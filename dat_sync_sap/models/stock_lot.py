from odoo import _, models, api,fields
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    _name = 'stock.lot'
    _inherit = ['stock.lot', 'abstract.sync.sap']

    @property
    def period_cron_xml_id(self):
        """XML ID of the cron job for periodic synchronization."""
        return 'dat_sync_sap.stock_lot_sync_cron_midnight'

    @property
    def api_route(self):
        return '/SerialNumber'

    @property
    def fields_mapping(self):
        return {
            'SerialNumber': 'name',
            'ItemCode': 'product_id.default_code',
            'BuyerCode': 'buyer_id.card_code',
            'OwnerCode': 'owner_id.card_code',
            'DeliveryDate': 'warranty_start_date',
            'WarrantyMonth': 'warranty_month',
            'SlpCode': 'saleperson_id.sap_slp_code',
        }

    def _get_or_create_product_for_serial(self, sap_values, serial_number):
        item_code = (sap_values.get('ItemCode') or '').strip()
        item_name = (sap_values.get('ItemName') or sap_values.get('ItemNameVN') or '').strip()
        default_code = item_code or serial_number
        product_name = item_name or default_code

        product = self._find_product_by_item_code(default_code)
        if product:
            return product

        product = self.env['product.product'].create({
            'name': product_name,
            'default_code': default_code,
        })
        _logger.warning(
            "Created missing product while syncing stock lot | serial=%s | item_code=%s | product_id=%s",
            serial_number,
            item_code,
            product.id,
        )
        return product

    def _find_product_by_item_code(self, item_code):
        item_code = (item_code or '').strip()
        if not item_code:
            return self.env['product.product']

        product = self.env['product.product'].search([('default_code', '=', item_code)], limit=1)
        if product:
            return product

        product = self.env['product.product'].search([('default_code', '=ilike', f'{item_code}(%')], limit=1)
        if product:
            return product

        return self.env['product.product'].search([('default_code', 'ilike', item_code)], limit=1)

    @property
    def identify_fields(self):
        return {'name'}

    def get_result(self, params=None, data=None, json=None, result_text=None, **kwargs) -> list:
        # Add Accept header to ensure JSON response
        headers = self.api_headers.copy()
        headers['Accept'] = 'application/json'

        # Initialize result list to collect all items
        sap_result = []
        json_body = dict(json or {})
        url = self.api_url + self.api_route
        use_paging = self.api_route == '/SerialNumber'

        # Ensure PageNumber and PageSize are set
        current_page = json_body.get('PageNumber', 1)
        page_size = json_body.get('PageSize', 1000)

        while True:
            if use_paging:
                json_body['PageNumber'] = current_page
                json_body['PageSize'] = page_size

            _logger.info(
                "Fetching stock lot SAP data | url=%s | page=%s | page_size=%s | body=%s",
                url,
                current_page if use_paging else '',
                page_size if use_paging else '',
                json_body,
            )

            response = self.api_method(
                url,
                headers=headers,
                json=json_body,
                **kwargs
            )

            if response.status_code != 200:
                response_text = getattr(response, 'text', '') or ''
                _logger.error(
                    "Stock lot SAP page failed | status=%s | body=%s",
                    response.status_code,
                    response_text[:1000],
                )
                raise UserError(_("Failed to get SAP stock lot data: HTTP %s - %s") % (
                    response.status_code,
                    response_text[:500],
                ))

            try:
                response_json = response.json()
            except MemoryError as error:
                _logger.exception(
                    "Stock lot SAP response is too large to parse | page=%s | page_size=%s",
                    current_page,
                    page_size,
                )
                raise UserError(_("SAP stock lot response is too large. Please reduce PageSize and run again: %s") % error)
            except ValueError as error:
                response_text = getattr(response, 'text', '') or ''
                _logger.exception("Stock lot SAP response is not valid JSON | body=%s", response_text[:1000])
                raise UserError(_("Failed to parse SAP stock lot response: %s") % error)

            if str(response_json.get('status', '')).upper() == 'FALSE':
                message = response_json.get('msg') or response_json.get('message') or response_json
                _logger.error(
                    "Stock lot SAP returned FALSE status | page=%s | message=%s",
                    current_page,
                    message,
                )
                raise UserError(_("SAP stock lot API returned FALSE status: %s") % message)

            result = response_json.get('result') or {}
            if isinstance(result, list):
                page_items = result
                total_pages = current_page
            else:
                page_items = result.get('Items') or []
                total_pages = result.get('TotalPages') or current_page

            sap_result.extend(page_items)
            _logger.info(
                "Fetched stock lot SAP data | page=%s | total_pages=%s | items=%s | total_items=%s",
                current_page if use_paging else '',
                total_pages if use_paging else '',
                len(page_items),
                len(sap_result),
            )

            # Check if there are more pages to fetch
            if not use_paging or current_page >= total_pages:
                break
            current_page += 1

        return sap_result

    def clean_odoo_field_value(self, fname: str, value):
        if fname.startswith(('product_id.', 'buyer_id.', 'owner_id.', 'saleperson_id.')):
            related_field = fname.split('.', 1)[1]
            if fname == 'product_id.default_code' and value:
                # Find product with matching default_code
                product = self.env['product.product'].search([('default_code', '=', value)], limit=1)
                if product:
                    return product.id  # Return product_id for product_id field
                serial_number = (self._context.get('sap_values') or {}).get('SerialNumber')
                product = self._get_or_create_product_for_serial(self._context.get('sap_values') or {}, serial_number)
                return product.id if product else False
            elif fname.startswith(('buyer_id.', 'owner_id.')):
                if related_field == 'card_code' and value:
                    # Find partners with matching card_code
                    partners = self.env['res.partner'].search([('card_code', '=', value)])
                    if not partners:
                        return False
                    if len(partners) == 1:
                        return partners.id
                    # If multiple partners, try to match with BuyerName
                    sap_values = self._context.get('sap_values', {})
                    buyer_name = sap_values.get('BuyerName')
                    if buyer_name:
                        for partner in partners:
                            if partner.sap_slp_name == buyer_name:
                                return partner.id
                    # If no match for BuyerName, return first partner
                    return partners[0].id
                elif related_field == 'sap_slp_name':
                    return value  # Handled in prepare_odoo_values for validation
            elif fname.startswith('saleperson_id.'):
                if related_field == 'sap_slp_code' and value:
                    # Find employee with matching sap_slp_code
                    employee = self.env['hr.employee'].search([('sap_slp_code', '=', value)], limit=1)
                    if employee:
                        return employee.id
                    return False
            return value
        # Handle direct fields
        return super().clean_odoo_field_value(fname, value)

    def check_allow_create(self, values: dict):
        if values.get('name') and self.search([('name', '=', values['name'])]).exists():
            return False
        return super().check_allow_create(values)

    def check_allow_update(self, values: dict):
        if values.get('name') and self.search([('name', '=', values['name'])]).exists():
            return False
        return super().check_allow_update(values)

    @api.model
    def sync_sap_data(self, json_data=None):
        self = self.sudo()
        if not json_data:
            raise UserError(_("Stock lot sync requires a date range. Please run the scheduled action or use the sync wizard with Start Date and End Date."))
        json_data = dict(json_data or {})
        json_data.setdefault("PageNumber", 1)
        json_data.setdefault("PageSize", 1000)
        sap_result = self.get_result(json=json_data)
        self._sync_sap_data(sap_result)

    @api.model
    def _sync_sap_data_for_period(self, start_dt, end_dt):
        end_dt = end_dt or fields.Datetime.now()
        month_start = end_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_start = max(start_dt or month_start, month_start)

        _logger.info(
            "Stock lot SAP monthly sync started | start=%s | end=%s",
            current_start,
            end_dt,
        )

        if current_start < end_dt:
            super()._sync_sap_data_for_period(current_start, end_dt)
            self.env.cr.commit()

        _logger.info(
            "Stock lot SAP monthly sync finished | start=%s | end=%s",
            current_start,
            end_dt,
        )

    def prepare_odoo_values(self, sap_values_list: list[dict]):
        stock_lot_env = self.env['stock.lot']
        table = stock_lot_env._table  # an toàn tên bảng ('stock_lot' hoặc 'stock_production_lot')
        cr = self.env.cr

        # 1) Thu thập serial hợp lệ (đã strip, khác rỗng)
        candidate_serials = {
            (d.get('SerialNumber') or '').strip()
            for d in sap_values_list
            if (d.get('SerialNumber') or '').strip()
        }
        if not candidate_serials:
            return [], []

        # 2) Tìm serial đã tồn tại trong DB bằng 1 câu SQL (tận dụng index)
        #    Dùng ANY(%s) để truyền 1 mảng thay vì IN với hàng chục ngàn placeholder.
        cr.execute(f"""
                SELECT name
                  FROM {table}
                 WHERE name = ANY(%s)
            """, (list(candidate_serials),))
        existing_serials = {row[0] for row in cr.fetchall()}

        # 3) Lọc payload (giữ thứ tự); serial đã có sẽ được cập nhật lại owner/buyer.
        seen_serials = set()
        values_create = []
        values_update = []
        for sap_values in sap_values_list:
            serial_number = (sap_values.get('SerialNumber') or '').strip()
            if not serial_number:
                continue
            if serial_number in seen_serials:
                continue
            seen_serials.add(serial_number)

            odoo_values = {}
            saleperson_id = None
            odoo_values['name'] = serial_number
            # Pass sap_values to context for use in clean_odoo_field_value
            self = self.with_context(sap_values=sap_values)
            for sap_field, value in sap_values.items():
                if sap_field not in self.fields_mapping or self.fields_mapping[sap_field] == '':
                    continue
                odoo_field = self.fields_mapping[sap_field]
                value_cleaned = self.clean_odoo_field_value(odoo_field, value)
                if odoo_field == 'product_id.default_code':
                    if value_cleaned:  # Only assign product_id if value_cleaned is valid
                        odoo_values['product_id'] = value_cleaned
                elif odoo_field == 'saleperson_id.sap_slp_code':
                    odoo_values['saleperson_id'] = value_cleaned if value_cleaned else False
                elif odoo_field == 'buyer_id.card_code':
                    if value_cleaned:
                        odoo_values['buyer_id'] = value_cleaned
                    if not sap_values.get('OwnerCode'):
                        if value_cleaned:
                            odoo_values['owner_id'] = value_cleaned
                elif odoo_field == 'owner_id.card_code':
                    if value_cleaned:
                        odoo_values['owner_id'] = value_cleaned
                else:
                    odoo_values[odoo_field] = value_cleaned
            if not odoo_values.get('warranty_start_date'):
                odoo_values.pop('warranty_start_date', None)
            if not odoo_values.get('product_id'):
                product = self._get_or_create_product_for_serial(sap_values, serial_number)
                if product:
                    odoo_values['product_id'] = product.id
            if serial_number in existing_serials:
                values_update.append(odoo_values)
            elif self.check_allow_create(odoo_values):
                values_create.append(odoo_values)
            else:
                _logger.warning("Skipped stock lot sync row after validation | serial=%s | values=%s | sap_values=%s",
                                serial_number, odoo_values, sap_values)
        return values_create, values_update

    def _sync_sap_data(self, sap_result):
        values_create, values_update = self.prepare_odoo_values(sap_result)
        created = 0
        updated = 0
        errors = []

        for values in values_create:
            try:
                with self.env.cr.savepoint():
                    self.create(values)
                    created += 1
            except Exception as e:
                _logger.exception("Create lot FAILED name=%s: %s", values.get('name'), e)
                errors.append("Create %s: %s" % (values.get('name'), e))

        for values in values_update:
            try:
                with self.env.cr.savepoint():
                    existing_lot = self.search([('name', '=', values.get('name'))], limit=1)
                    if existing_lot:
                        existing_lot.write(values)
                        updated += 1
            except Exception as e:
                _logger.exception("Update lot FAILED name=%s: %s", values.get('name'), e)
                errors.append("Update %s: %s" % (values.get('name'), e))
        _logger.info(
            "Stock lot SAP sync finished | input=%s | create=%s | update=%s | errors=%s",
            len(sap_result or []),
            created,
            updated,
            len(errors),
        )
        if errors:
            _logger.error("Stock lot SAP sync completed with errors: %s", "; ".join(errors[:50]))
