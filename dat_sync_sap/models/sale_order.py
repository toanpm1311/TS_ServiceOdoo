import logging
from datetime import datetime, timedelta

from odoo import _, models, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

STORE_CITY_XML = {
    '1': 'dat_website_helpdesk.dat_company_mn',
    '2': 'dat_website_helpdesk.dat_company_mt',
    '3': 'dat_website_helpdesk.dat_company_mb',
}

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'abstract.sync.sap']

    @property
    def api_route(self):
        return '/GetAvailableInventory'

    def action_update_stock(self):
        for order in self:
            if not order.order_line:
                raise UserError(_('Please add at least one order line before check on hand quantity.'))
            product_warehouse_pairs = order.get_product_warehouse_list()
            stock_data = self.sync_stock_data(product_warehouse_pairs)
            if not stock_data:
                continue

            stock_by_pair, stock_by_item = order._prepare_available_stock_maps(stock_data)

            for line in order.order_line:
                if not order._is_stock_check_inventory_line(line):
                    continue
                code = order._get_stock_product_code(line)
                warehouse_code = order._get_stock_warehouse_code(line)
                qty = stock_by_pair.get((code, warehouse_code))
                if qty is None:
                    qty = stock_by_item.get(code, 0)
                    _logger.info(
                        "SAP stock check fallback by item only | order=%s | line=%s | item=%s | warehouse=%s | qty=%s",
                        order.name or order.id,
                        line.id,
                        code,
                        warehouse_code,
                        qty,
                    )
                line.onhand_quantity = qty

        return True

    def action_sync_sap_customer_data(self):
        self.ensure_one()
        return self.env['res.partner'].action_sync_sap_customer_data()

    def _is_stock_check_inventory_line(self, line):
        if line.display_type or not line.product_id:
            return False
        product = line.product_id
        product_type = (
            getattr(product, 'detailed_type', False)
            or getattr(product.product_tmpl_id, 'detailed_type', False)
            or getattr(product, 'type', False)
        )
        if product_type == 'service':
            line.onhand_quantity = 0
            return False
        return True

    def _get_stock_product_code(self, line):
        return (
            line.product_id.product_tmpl_id.default_code
            or line.product_id.default_code
            or ''
        ).strip()

    def _get_stock_warehouse_code(self, line):
        warehouse = line.filler_warehouse_id or line.order_id.filler_warehouse_id
        return (warehouse.code or '').strip() if warehouse else ''

    def _get_stock_row_item_code(self, row):
        return str(row.get('ItemCode') or row.get('Item') or '').strip()

    def _get_stock_row_warehouse_code(self, row):
        return str(
            row.get('WhsCode')
            or row.get('WarehouseCode')
            or row.get('Warehouse')
            or row.get('Kho')
            or ''
        ).strip()

    def _get_stock_row_available_qty(self, row):
        try:
            return float(row.get('TonKhaDung') or 0)
        except (TypeError, ValueError):
            return 0.0

    def _prepare_available_stock_maps(self, stock_data):
        stock_by_pair = {}
        stock_by_item = {}
        for item in stock_data or []:
            code = self._get_stock_row_item_code(item)
            warehouse_code = self._get_stock_row_warehouse_code(item)
            qty = self._get_stock_row_available_qty(item)
            if not code:
                continue
            stock_by_item[code] = qty
            if warehouse_code:
                stock_by_pair[(code, warehouse_code)] = qty
        return stock_by_pair, stock_by_item

    def product_warehouse_pairs(self):
        """Backward-compatible alias for callers expecting the old helper name."""
        return self.get_product_warehouse_list()

    def get_product_warehouse_list(self):
        result = []
        for line in self.order_line:
            if not self._is_stock_check_inventory_line(line):
                continue
            product_code = self._get_stock_product_code(line)
            if not product_code:
                raise UserError(_('Product %s in order line %s does not have SAP model defined') % (line.product_id.name, line.id))
            warehouse_code = self._get_stock_warehouse_code(line)
            if product_code and warehouse_code:
                result.append({
                    'product_code': product_code,
                    'warehouse_code': warehouse_code
                })
        return result

    @api.model
    def sync_stock_data(self, product_warehouse_pairs: list[dict]):
        try:
            if not product_warehouse_pairs:
                return []
            # Group by warehouse to optimize API calls
            warehouse_groups = {}
            for pair in product_warehouse_pairs:
                warehouse_code = pair['warehouse_code']
                product_code = pair['product_code']
                if warehouse_code not in warehouse_groups:
                    warehouse_groups[warehouse_code] = []
                warehouse_groups[warehouse_code].append(product_code)

            results = []
            for warehouse_code, product_codes in warehouse_groups.items():
                list_product_code_str = ",".join(dict.fromkeys(product_codes))
                json_vendor_data = {
                    "Item": list_product_code_str,
                    "WarehouseCode": warehouse_code
                }
                _logger.info(
                    "SAP stock check request | warehouse=%s | products=%s | payload=%s",
                    warehouse_code,
                    product_codes,
                    json_vendor_data,
                )
                sap_vendor_result = self.get_result(json=json_vendor_data, result_text='ListAvailableInventory')
                if not isinstance(sap_vendor_result, list):
                    raise UserError(_('Invalid response format from SAP for warehouse %s: Expected list') % warehouse_code)
                for row in sap_vendor_result:
                    row = dict(row or {})
                    row.setdefault('WarehouseCode', warehouse_code)
                    results.append(row)
                _logger.info(
                    "SAP stock check response | warehouse=%s | row_count=%s | rows=%s",
                    warehouse_code,
                    len(sap_vendor_result),
                    sap_vendor_result,
                )

            return results
        except UserError as err:
            raise UserError(str(err))
        except Exception as e:
            raise UserError(_('Failed to get SAP data: %s') % str(e))

    @api.model
    def sync_status_for_period(self):
        self = self.sudo()
        search_domain = []
        sale_orders = self.search(search_domain)
        for so in sale_orders:
            response = self.api_method(
                self.api_url + '/GetStatusSO',
                headers=self.api_headers,
                json={'SO': so.name})
            if response.status_code == 200:
                sap_result = response.json().get('result')
                if not sap_result:
                    continue
                so.sap_status = sap_result[-1].get('DocStatus')
                self.env.cr.commit()
            else:
                raise UserError(_("Failed to get SAP data: %s") % response.reason)
