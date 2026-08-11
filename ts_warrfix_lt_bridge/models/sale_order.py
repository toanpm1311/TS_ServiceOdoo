import logging
import json
import re
from collections import defaultdict
import requests
import odoo
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.addons.dat_sap_config.tools.sap import (
    get_sap_request_body_bool,
    get_sap_request_body_date,
    get_sap_request_body_html,
)
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    LT_INVENTORY_API = '/GetAvailableInventory_LT'
    SO_MAIN_API = '/CreateSOForWarrFix'
    SO_LT_API = '/CreateSOForWarrFix_LT'
    DXVT_MAIN_API = '/CreateITRForWarrFix'
    DXVT_LT_API = '/CreateITRForWarrFix_LT'

    ts_main_so_doc_number = fields.Char(string='Main SO Doc Number', copy=False)
    ts_main_dxvt_doc_number = fields.Char(string='Main DXVT Doc Number', copy=False)
    ts_lt_so_doc_number = fields.Char(string='LT SO Doc Number', copy=False)
    ts_lt_dxvt_doc_number = fields.Char(string='LT DXVT Doc Number', copy=False)
    ts_split_doc_note = fields.Char(string='Split SAP SO Note', copy=False)
    ts_split_dxvt_note = fields.Char(string='Split SAP DXVT Note', copy=False)
    ts_split_sap_doc_state = fields.Text(string='Split SAP Doc State', copy=False)

    @api.model
    def _register_hook(self):
        res = super()._register_hook()
        model_cls = self.env['sale.order'].__class__

        if not getattr(model_cls, '_ts_lt_bridge_action_update_stock_patched', False):
            original_action_update_stock = getattr(model_cls, 'action_update_stock', None)
            if not original_action_update_stock:
                _logger.warning(
                    '[LT_STOCK_DISPLAY] skip action_update_stock patch because method is missing on sale.order'
                )
            else:
                def _patched_action_update_stock(records, *args, **kwargs):
                    _logger.warning(
                        '[LT_STOCK_DISPLAY] patched action_update_stock hit | orders=%s | args=%s | kwargs=%s',
                        records.ids, args, kwargs,
                    )
                    result = original_action_update_stock(records, *args, **kwargs)
                    try:
                        records._ts_after_action_update_stock_lt()
                    except Exception:
                        _logger.exception(
                            '[LT_STOCK_DISPLAY] patched action_update_stock failed in LT bridge | orders=%s',
                            records.ids,
                        )
                    return result

                model_cls.action_update_stock = _patched_action_update_stock
                model_cls._ts_lt_bridge_action_update_stock_patched = True
                _logger.warning('[LT_STOCK_DISPLAY] action_update_stock patched on sale.order')

        if not getattr(model_cls, '_ts_lt_bridge_create_sap_doc_patched', False):
            original_create_sap_doc = getattr(model_cls, 'create_sap_doc', None)
            if not original_create_sap_doc:
                _logger.warning(
                    '[LT_STOCK_DISPLAY] skip create_sap_doc patch because method is missing on sale.order'
                )
            else:
                def _patched_create_sap_doc(records, *args, **kwargs):
                    doc_type = kwargs.get('doc_type')
                    if doc_type is None and args:
                        doc_type = args[0]
                    _logger.warning(
                        '[LT_STOCK_DISPLAY] patched create_sap_doc hit | orders=%s | doc_type=%s',
                        records.ids, doc_type,
                    )
                    return records._ts_create_sap_doc_bridge(
                        original_create_sap_doc,
                        doc_type=doc_type or 'SO',
                    )

                model_cls.create_sap_doc = _patched_create_sap_doc
                model_cls._ts_lt_bridge_create_sap_doc_patched = True
                _logger.warning('[LT_STOCK_DISPLAY] create_sap_doc patched on sale.order')

        if not getattr(model_cls, '_ts_lt_bridge_action_create_sap_so_batch_patched', False):
            original_action_create_sap_so_batch = getattr(model_cls, 'action_create_sap_so_batch', None)
            if not original_action_create_sap_so_batch:
                _logger.warning(
                    '[LT_SPLIT_SO_BATCH] skip action_create_sap_so_batch patch because method is missing on sale.order'
                )
            else:
                def _patched_action_create_sap_so_batch(records, *args, **kwargs):
                    _logger.warning(
                        '[LT_SPLIT_SO_BATCH] patched action_create_sap_so_batch hit | orders=%s',
                        records.ids,
                    )
                    return records._ts_action_create_sap_so_batch_bridge(
                        original_action_create_sap_so_batch,
                    )

                model_cls.action_create_sap_so_batch = _patched_action_create_sap_so_batch
                model_cls._ts_lt_bridge_action_create_sap_so_batch_patched = True
                _logger.warning('[LT_SPLIT_SO_BATCH] action_create_sap_so_batch patched on sale.order')

        return res

    @property
    def api_route(self):
        forced = self.env.context.get('force_api_route')
        if forced:
            return forced
        try:
            return super().api_route
        except Exception:
            return '/GetAvailableInventory'

    def _use_lt_stock_display_bridge(self):
        self.ensure_one()
        if 'ticket_id' in self._fields:
            return bool(self.ticket_id)
        return True

    def _float_or_zero(self, value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _extract_item_code_from_lt_row(self, row):
        return str(
            row.get('ItemCode')
            or row.get('itemCode')
            or row.get('Item')
            or row.get('MaHang')
            or ''
        ).strip()

    def _extract_whs_code_from_lt_row(self, row):
        return str(
            row.get('WhsCode')
            or row.get('WarehouseCode')
            or row.get('Whs')
            or row.get('Kho')
            or row.get('Warehouse')
            or ''
        ).strip()

    def _extract_available_qty_from_lt_row(self, row):
        return self._float_or_zero(
            row.get('TonKhaDung')
            if row.get('TonKhaDung') is not None
            else row.get('AvailableQty')
            if row.get('AvailableQty') is not None
            else row.get('Quantity')
            if row.get('Quantity') is not None
            else row.get('OnHand')
            if row.get('OnHand') is not None
            else 0
        )

    def _get_product_codes_for_lt(self):
        self.ensure_one()
        codes = []
        for line in self.order_line.filtered(lambda l: not l.display_type and l.product_id):
            code = (line.product_id.default_code or '').strip()
            if code and code not in codes:
                codes.append(code)
        return codes

    def _prepare_lt_inventory_payload(self, product_code, warehouse_code):
        payload = {'Item': product_code or ''}
        if warehouse_code:
            payload['WarehouseCode'] = warehouse_code
        return payload

    def _call_lt_inventory_api(self, product_code, warehouse_code=''):
        self.ensure_one()
        if not product_code:
            _logger.warning('[LT_STOCK_DISPLAY] Skip LT API because product_code is empty | SO=%s', self.name or self.id)
            return []

        payload = self._prepare_lt_inventory_payload(product_code, warehouse_code)
        url = (getattr(self, 'api_url', False) or '').rstrip('/') + self.LT_INVENTORY_API
        headers = dict(getattr(self, 'api_headers', None) or {})
        safe_headers = {k: ('***' if 'auth' in k.lower() or 'token' in k.lower() else v) for k, v in headers.items()}
        _logger.warning('[LT_STOCK_DISPLAY] LT API call start | SO=%s | method=GET | url=%s | payload=%s | headers=%s',
                        self.name or self.id, url, payload, safe_headers)
        if not url:
            _logger.error('[LT_STOCK_DISPLAY] Missing api_url for LT API | SO=%s', self.name or self.id)
            return []

        try:
            response = requests.request(
                'GET',
                url,
                headers=headers,
                json=payload,
                timeout=60,
            )
            _logger.warning('[LT_STOCK_DISPLAY] LT raw response | SO=%s | status=%s | reason=%s | text=%s',
                            self.name or self.id, response.status_code, response.reason, response.text)
            response.raise_for_status()
            data = response.json() or {}
            rows = data.get('ListAvailableInventory') or data.get('result') or data.get('data') or []
        except Exception:
            _logger.exception('[LT_STOCK_DISPLAY] Failed LT direct GET | SO=%s | url=%s | payload=%s', self.name or self.id, url, payload)
            return []

        for row in rows:
            if warehouse_code and not self._extract_whs_code_from_lt_row(row):
                row['WhsCode'] = warehouse_code

        _logger.info('[LT_STOCK_DISPLAY] LT API ok | SO=%s | payload=%s | row_count=%s | rows=%s', self.name or self.id, payload, len(rows), rows)
        return rows

    def _group_lt_inventory_by_item_and_wh(self, stock_data):
        self.ensure_one()
        grouped = defaultdict(lambda: defaultdict(float))
        for row in stock_data or []:
            item_code = self._extract_item_code_from_lt_row(row)
            whs_code = self._extract_whs_code_from_lt_row(row)
            qty = self._extract_available_qty_from_lt_row(row)
            if not item_code:
                continue
            grouped[item_code][whs_code or ''] += qty
        return grouped

    def _extract_bracket_wh_code(self, value):
        text = str(value or '').strip()
        if not text:
            return ''
        match = re.search(r'\[\s*([A-Za-z0-9_-]+)\s*\]', text)
        if match:
            return (match.group(1) or '').strip().upper()
        return ''

    def _is_sap_wh_code(self, value):
        code = str(value or '').strip().upper()
        if not code or ' ' in code:
            return False
        return any(ch.isalpha() for ch in code) and any(ch.isdigit() for ch in code)

    def _normalize_wh_code(self, value):
        if value in (None, False, ''):
            return ''
        bracket_code = self._extract_bracket_wh_code(value)
        if bracket_code:
            return bracket_code
        text = str(value).strip().upper()
        if self._is_sap_wh_code(text):
            return text
        return ''

    def _get_line_current_warehouse_code_for_lt(self, line):
        self.ensure_one()
        candidates = [
            # Material warehouse should be prioritized over service/location warehouse
            getattr(getattr(line, 'filler_warehouse_id', False), 'code', False),
            getattr(getattr(self, 'filler_warehouse_id', False), 'code', False),
            getattr(getattr(line, 'filler_warehouse_id', False), 'display_name', False),
            getattr(getattr(self, 'filler_warehouse_id', False), 'display_name', False),
            getattr(getattr(line, 'filler_warehouse_id', False), 'name', False),
            getattr(getattr(self, 'filler_warehouse_id', False), 'name', False),

            getattr(getattr(line, 'warehouse_id', False), 'code', False),
            getattr(getattr(self, 'warehouse_id', False), 'code', False),
            getattr(getattr(line, 'warehouse_id', False), 'display_name', False),
            getattr(getattr(self, 'warehouse_id', False), 'display_name', False),
            getattr(getattr(line, 'warehouse_id', False), 'name', False),
            getattr(getattr(self, 'warehouse_id', False), 'name', False),
        ]
        for raw in candidates:
            code = self._normalize_wh_code(raw)
            if code:
                return code
        _logger.warning(
            '[LT_STOCK_DISPLAY] Cannot resolve SAP warehouse code | SO=%s | line_id=%s | raw_candidates=%s',
            self.name or self.id,
            getattr(line, 'id', False),
            candidates,
        )
        return ''

    def _get_paired_lt_warehouse_code(self, current_code):
        """Kept only for backward compatibility / debug; LT stock now uses the same SAP warehouse code.

        The real API behavior validated by the user is:
        - main stock API and LT stock API both receive the material warehouse SAP code
        - e.g. Item=17001-03684 + WarehouseCode=HCMVP201 returns LT=1
        So we no longer auto-swap 01 <-> 20 during LT stock checking.
        """
        code = (current_code or '').strip().upper()
        if not code:
            return ''
        if code.endswith('01'):
            return code[:-2] + '20'
        if code.endswith('20'):
            return code[:-2] + '01'
        return ''

    def _get_line_lt_inventory_warehouse_code(self, line):
        self.ensure_one()
        current_wh = self._get_line_current_warehouse_code_for_lt(line)
        paired_wh = self._get_paired_lt_warehouse_code(current_wh)
        # User-validated behavior in this environment:
        # LT inventory API must receive the SAME material warehouse code shown on the line
        # (example: Item=17001-03684, WarehouseCode=HCMVP201 returns TonKhaDung=1).
        # So we do not swap to the paired warehouse during LT stock checking.
        lt_wh = current_wh
        _logger.info(
            '[LT_STOCK_DISPLAY] Resolve LT warehouse | SO=%s | line_id=%s | product=%s | current_wh=%s | paired_wh=%s | chosen_lt_wh=%s | strategy=same_current_wh',
            self.name or self.id,
            line.id,
            (line.product_id.default_code or '').strip(),
            current_wh,
            paired_wh,
            lt_wh,
        )
        return lt_wh


    def _get_lt_side_qty_for_line(self, line):
        self.ensure_one()
        if not line.product_id or not line.product_id.default_code:
            _logger.warning('[LT_STOCK_DISPLAY] Skip LT qty because line has no product/default_code | SO=%s | line_id=%s', self.name or self.id, line.id)
            return 0.0

        item_code = (line.product_id.default_code or '').strip()
        current_wh = self._get_line_current_warehouse_code_for_lt(line)
        lt_wh = self._get_line_lt_inventory_warehouse_code(line)
        if not lt_wh:
            _logger.warning('[LT_STOCK_DISPLAY] Skip LT qty because lt_wh is empty | SO=%s | line_id=%s | item=%s | current_wh=%s', self.name or self.id, line.id, item_code, current_wh)
            return 0.0

        stock_data = self._call_lt_inventory_api(item_code, lt_wh)
        qty = 0.0
        matched_rows = []
        for row in stock_data or []:
            row_item_code = self._extract_item_code_from_lt_row(row)
            row_wh = self._extract_whs_code_from_lt_row(row) or lt_wh
            row_qty = self._extract_available_qty_from_lt_row(row)
            is_match = row_item_code == item_code and row_wh == lt_wh
            matched_rows.append({
                'row_item_code': row_item_code,
                'row_wh': row_wh,
                'row_qty': row_qty,
                'is_match': is_match,
                'raw': row,
            })
            if is_match:
                qty += row_qty

        _logger.info(
            '[LT_STOCK_DISPLAY] LT qty resolved | SO=%s | line_id=%s | item=%s | current_wh=%s | lt_wh=%s | matched_qty=%s | matched_rows=%s',
            self.name or self.id,
            line.id,
            item_code,
            current_wh,
            lt_wh,
            qty,
            matched_rows,
        )
        return qty

    def _ts_after_action_update_stock_lt(self):
        _logger.warning('[LT_STOCK_DISPLAY] _ts_after_action_update_stock_lt start | orders=%s', self.ids)
        res = True

        for order in self.filtered(lambda so: so._use_lt_stock_display_bridge()):
            product_codes = order._get_product_codes_for_lt()
            target_lines = order.order_line.filtered(lambda l: not l.display_type and l.product_id).sorted(key=lambda l: l.id)
            _logger.info('[LT_STOCK_DISPLAY] process order | SO=%s | product_codes=%s | target_line_ids=%s', order.name or order.id, product_codes, target_lines.ids)

            # Always reset LT-related fields first to avoid stale values appearing on the wrong line
            for line in target_lines:
                vals = {
                    'lt_side_qty': 0.0,
                    'lt_lt_qty': 0.0,
                    'lt_main_qty': order._float_or_zero(getattr(line, 'onhand_quantity', 0.0)),
                    'ts_alloc_main_qty': 0.0,
                    'ts_alloc_lt_qty': 0.0,
                    'ts_supply_side': False,
                }
                if 'lt_warehouse_code' in line._fields:
                    vals['lt_warehouse_code'] = ''
                line.write(vals)

            if not product_codes:
                _logger.warning('[LT_STOCK_DISPLAY] No product codes to check LT stock | SO=%s', order.name or order.id)
                continue

            try:
                _logger.info('[LT_STOCK_DISPLAY] action_update_stock start | SO=%s | lines=%s', order.name or order.id, len(target_lines))
                resolved_by_line = {}
                for line in target_lines:
                    item_code = (line.product_id.default_code or '').strip()
                    current_wh = order._get_line_current_warehouse_code_for_lt(line)
                    lt_wh = order._get_line_lt_inventory_warehouse_code(line)
                    main_qty = order._float_or_zero(getattr(line, 'onhand_quantity', 0.0))
                    _logger.info('[LT_STOCK_DISPLAY] line before LT check | SO=%s | line_id=%s | item=%s | qty=%s | current_wh=%s | main_onhand=%s | chosen_lt_wh=%s',
                                 order.name or order.id, line.id, item_code, line.product_uom_qty, current_wh, main_qty, lt_wh)
                    lt_qty = order._get_lt_side_qty_for_line(line)
                    resolved_by_line[line.id] = {
                        'item_code': item_code,
                        'current_wh': current_wh,
                        'lt_wh': lt_wh,
                        'main_qty': main_qty,
                        'lt_qty': lt_qty,
                    }
                    vals = {
                        'lt_side_qty': lt_qty,
                        'lt_lt_qty': lt_qty,
                        'lt_main_qty': main_qty,
                    }
                    if 'lt_warehouse_code' in line._fields:
                        vals['lt_warehouse_code'] = lt_wh
                    line.write(vals)
                    _logger.info('[LT_STOCK_DISPLAY] line write LT fields | SO=%s | line_id=%s | vals=%s',
                                 order.name or order.id, line.id, vals)
                    _logger.info('[LT_STOCK_DISPLAY] line after LT check | SO=%s | line_id=%s | item=%s | main_qty=%s | lt_qty=%s | lt_wh=%s',
                                 order.name or order.id, line.id, item_code, main_qty, lt_qty, lt_wh)

                order.invalidate_recordset()
                order._ts_prepare_split_allocations()
                for line in target_lines:
                    info = resolved_by_line.get(line.id, {})
                    _logger.info('[LT_STOCK_DISPLAY] allocation result | SO=%s | line_id=%s | item=%s | requested=%s | main_stock=%s | lt_stock=%s | alloc_main=%s | alloc_lt=%s | side=%s',
                                 order.name or order.id, line.id, info.get('item_code') or (line.product_id.default_code or '').strip(), line.product_uom_qty,
                                 order._ts_get_available_main_qty(line), order._ts_get_available_lt_qty(line),
                                 line.ts_alloc_main_qty, line.ts_alloc_lt_qty, line.ts_supply_side)
            except Exception:
                _logger.exception('[LT_STOCK_DISPLAY] Failed to update LT side stock | SO=%s', order.name or order.id)
                for line in target_lines:
                    vals = {
                        'lt_side_qty': 0.0,
                        'lt_lt_qty': 0.0,
                        'lt_main_qty': order._float_or_zero(getattr(line, 'onhand_quantity', 0.0)),
                        'ts_alloc_main_qty': 0.0,
                        'ts_alloc_lt_qty': 0.0,
                        'ts_supply_side': False,
                    }
                    if 'lt_warehouse_code' in line._fields:
                        vals['lt_warehouse_code'] = order._get_line_lt_inventory_warehouse_code(line)
                    line.write(vals)
        return res

    def _ts_get_available_main_qty(self, line):
        self.ensure_one()
        return self._float_or_zero(getattr(line, 'lt_main_qty', 0.0) or getattr(line, 'onhand_quantity', 0.0))

    def _ts_get_available_lt_qty(self, line):
        self.ensure_one()
        return self._float_or_zero(getattr(line, 'lt_lt_qty', 0.0) or getattr(line, 'lt_side_qty', 0.0))

    def _ts_get_requested_qty(self, line):
        self.ensure_one()
        return self._float_or_zero(getattr(line, 'product_uom_qty', 0.0))

    def _ts_allocate_line_between_main_lt(self, line):
        self.ensure_one()
        requested = self._ts_get_requested_qty(line)
        main_qty = self._ts_get_available_main_qty(line)
        lt_qty = self._ts_get_available_lt_qty(line)

        result = {
            'requested_qty': requested,
            'available_main_qty': main_qty,
            'available_lt_qty': lt_qty,
            'main_qty': 0.0,
            'lt_qty': 0.0,
            'side': False,
        }

        if requested <= 0:
            return result

        main_enough = main_qty >= requested
        lt_enough = lt_qty >= requested

        if main_enough and lt_enough:
            if main_qty >= lt_qty:
                result.update({'main_qty': requested, 'side': 'main'})
            else:
                result.update({'lt_qty': requested, 'side': 'lt'})
            return result

        if main_enough:
            result.update({'main_qty': requested, 'side': 'main'})
            return result

        if lt_enough:
            result.update({'lt_qty': requested, 'side': 'lt'})
            return result

        if main_qty > 0 and lt_qty > 0 and (main_qty + lt_qty) >= requested:
            if main_qty >= lt_qty:
                alloc_main = min(main_qty, requested)
                alloc_lt = requested - alloc_main
            else:
                alloc_lt = min(lt_qty, requested)
                alloc_main = requested - alloc_lt
            result.update({'main_qty': alloc_main, 'lt_qty': alloc_lt, 'side': 'split'})
            return result

        if main_qty >= lt_qty:
            result.update({'main_qty': requested, 'side': 'fallback_main'})
        else:
            result.update({'lt_qty': requested, 'side': 'fallback_lt'})
        return result

    def _ts_prepare_split_allocations(self):
        self.ensure_one()
        for line in self.order_line.filtered(lambda l: not l.display_type and l.product_id):
            alloc = self._ts_allocate_line_between_main_lt(line)
            line.ts_alloc_main_qty = alloc['main_qty']
            line.ts_alloc_lt_qty = alloc['lt_qty']
            line.ts_supply_side = alloc['side']
            _logger.info('[LT_STOCK_DISPLAY] prepare allocation | SO=%s | line_id=%s | item=%s | alloc=%s',
                         self.name or self.id, line.id, (line.product_id.default_code or '').strip(), alloc)
        return True

    def _ts_line_allowed_for_doc_type(self, line, doc_type='SO'):
        self.ensure_one()
        if line.display_type or not line.product_id:
            return False
        if doc_type != 'DXVT':
            return True
        if 'create_sap' in line._fields and not line.create_sap:
            return False
        product_type = getattr(line.product_id, 'detailed_type', False) or getattr(line.product_id, 'type', False)
        if product_type == 'service':
            _logger.info(
                '[LT_SPLIT_DXVT] Skip service/non-inventory line | SO=%s | line_id=%s | product=%s | code=%s',
                self.name or self.id,
                line.id,
                line.product_id.display_name,
                line.product_id.default_code or '',
            )
            return False
        return True

    def _ts_is_repair_flow(self):
        self.ensure_one()
        ticket = getattr(self, 'ticket_id', False)
        if not ticket:
            return False
        return bool(
            getattr(ticket, 'request_type', False) == 'repair'
            or getattr(ticket, 'product_warranty_status', False) in ('out_of_warranty', 'not_eligible_for_warranty')
            or getattr(ticket, 'service_action', False) in ('repair_at_dat', 'repair_onsite')
        )

    def _ts_get_main_product(self):
        self.ensure_one()
        product = getattr(self, 'main_product_id', False)
        if product:
            return product
        ticket = getattr(self, 'ticket_id', False)
        if ticket:
            lot = getattr(ticket, 'new_stock_lot_id', False) or getattr(ticket, 'stock_lot_id', False)
            return getattr(lot, 'product_id', False) or getattr(ticket, 'product_id', False)
        return self.env['product.product']

    def _ts_is_main_product_line(self, line):
        self.ensure_one()
        main_product = self._ts_get_main_product()
        if main_product and line.product_id == main_product:
            return True
        product_type = getattr(line.product_id, 'detailed_type', False) or getattr(line.product_id, 'type', False)
        product_text = '%s %s' % (line.product_id.display_name or '', line.name or '')
        if ('create_sap' in line._fields and not line.create_sap) or (
            product_type == 'service' and 'fixing' in product_text.casefold()
        ):
            return False
        main_code = (
            getattr(self, 'main_product_code', False)
            or getattr(main_product, 'default_code', False)
            or ''
        ).strip()
        line_code = (
            getattr(getattr(line, 'product_template_id', False), 'default_code', False)
            or getattr(line.product_id, 'default_code', False)
            or ''
        ).strip()
        return bool(main_code and line_code and main_code == line_code)

    def _ts_is_lt_replacement_placeholder_line(self, line):
        self.ensure_one()
        if self._ts_is_main_product_line(line):
            return False
        if 'create_sap' in line._fields and not line.create_sap:
            return True
        product_type = getattr(line.product_id, 'detailed_type', False) or getattr(line.product_id, 'type', False)
        product_text = '%s %s' % (line.product_id.display_name or '', line.name or '')
        return product_type == 'service' and 'fixing' in product_text.casefold()

    def _ts_has_lt_replacement_placeholder_lines(self):
        self.ensure_one()
        return bool(self.order_line.filtered(
            lambda line: not line.display_type
            and line.product_id
            and self._ts_is_lt_replacement_placeholder_line(line)
        ))

    def _ts_split_material_entries_by_side(self, doc_type='SO'):
        self.ensure_one()
        main_entries = []
        lt_entries = []
        for line in self.order_line.filtered(lambda l: self._ts_line_allowed_for_doc_type(l, doc_type=doc_type)):
            if self._ts_is_main_product_line(line) or self._ts_is_lt_replacement_placeholder_line(line):
                continue

            alloc = self._ts_allocate_line_between_main_lt(line)
            current_wh = self._get_line_current_warehouse_code_for_lt(line)
            lt_wh = self._get_line_lt_inventory_warehouse_code(line)

            if alloc['main_qty'] > 0:
                main_entries.append({
                    'line': line,
                    'quantity': alloc['main_qty'],
                    'warehouse_code': current_wh,
                    'allocation': alloc,
                    'side': 'main',
                })
            if alloc['lt_qty'] > 0:
                lt_entries.append({
                    'line': line,
                    'quantity': alloc['lt_qty'],
                    'warehouse_code': lt_wh,
                    'allocation': alloc,
                    'side': 'lt',
                })
        return main_entries, lt_entries

    def _ts_prepare_whole_line_entry(self, line, side='main'):
        self.ensure_one()
        warehouse_code = (
            self._get_line_lt_inventory_warehouse_code(line)
            if side == 'lt'
            else self._get_line_current_warehouse_code_for_lt(line)
        )
        return {
            'line': line,
            'quantity': self._ts_get_requested_qty(line),
            'warehouse_code': warehouse_code,
            'allocation': {
                'requested_qty': self._ts_get_requested_qty(line),
                'main_qty': self._ts_get_requested_qty(line) if side == 'main' else 0.0,
                'lt_qty': self._ts_get_requested_qty(line) if side == 'lt' else 0.0,
                'side': side,
            },
            'side': side,
        }

    def _ts_prepare_allocated_line_entries(self, line, allocation=None):
        self.ensure_one()
        allocation = allocation or self._ts_allocate_line_between_main_lt(line)
        current_wh = self._get_line_current_warehouse_code_for_lt(line)
        lt_wh = self._get_line_lt_inventory_warehouse_code(line)
        entries = []

        if allocation.get('main_qty', 0.0) > 0:
            entries.append({
                'line': line,
                'quantity': allocation['main_qty'],
                'warehouse_code': current_wh,
                'allocation': allocation,
                'side': 'main',
            })
        if allocation.get('lt_qty', 0.0) > 0:
            entries.append({
                'line': line,
                'quantity': allocation['lt_qty'],
                'warehouse_code': lt_wh,
                'allocation': allocation,
                'side': 'lt',
            })
        return entries

    def _ts_get_component_warehouse_side(self, main_entries, lt_entries):
        self.ensure_one()
        has_main = bool(main_entries)
        has_lt = bool(lt_entries)
        if has_main and has_lt:
            return 'split'
        if has_main and not has_lt:
            return 'main'
        if has_lt and not has_main:
            return 'lt'
        return False

    def _ts_get_line_allocated_side(self, line):
        self.ensure_one()
        allocation = self._ts_allocate_line_between_main_lt(line)
        if allocation.get('main_qty', 0.0) > 0 and not allocation.get('lt_qty', 0.0):
            return 'main'
        if allocation.get('lt_qty', 0.0) > 0 and not allocation.get('main_qty', 0.0):
            return 'lt'
        if allocation.get('main_qty', 0.0) > 0 and allocation.get('lt_qty', 0.0) > 0:
            return 'split'
        return False

    def _ts_get_main_product_warehouse_side(self, line, main_entries, lt_entries, bnk_side=False):
        self.ensure_one()
        component_side = self._ts_get_component_warehouse_side(main_entries, lt_entries)
        return (
            bnk_side
            or (component_side if component_side in ('main', 'lt') else False)
            or self._ts_get_line_allocated_side(line)
            or 'main'
        )

    def _ts_get_ticket_bnk_warehouse_side(self):
        """Return the warehouse side used by the ticket's latest successful BnK flow."""
        self.ensure_one()
        ticket = getattr(self, 'ticket_id', False)
        if not ticket:
            return False

        stored_side = getattr(ticket, 'bnk_warehouse_side', False)
        if stored_side in ('main', 'lt'):
            return stored_side

        # Backward compatibility for tickets processed before the side field
        # existed: infer it from the latest successful BnK chatter entry.
        messages = self.env['mail.message'].sudo().search([
            ('model', '=', 'ticket.helpdesk'),
            ('res_id', '=', ticket.id),
            ('body', 'ilike', 'BnK'),
        ], order='date desc, id desc', limit=20)
        for message in messages:
            match = re.search(r'BnK\s+(/[A-Za-z0-9_]+)', str(message.body or ''), re.IGNORECASE)
            if not match:
                continue
            api_path = match.group(1).rstrip('/').upper()
            return 'lt' if api_path.endswith('LT') else 'main'
        return False

    def _ts_selected_lines_by_side(self, doc_type='SO'):
        self.ensure_one()
        main_entries, lt_entries = self._ts_split_material_entries_by_side(doc_type=doc_type)
        is_dxvt = doc_type == 'DXVT'
        main_product_sides = set()
        bnk_side = self._ts_get_ticket_bnk_warehouse_side()

        main_product_lines = self.order_line.filtered(
            lambda l: (
                self._ts_line_allowed_for_doc_type(l, doc_type=doc_type)
                and self._ts_is_main_product_line(l)
            )
        )
        for line in main_product_lines:
            # Stable priority for the main product:
            # 1) the side where BnK already received the ticket product
            # 2) the pure side selected by component stock allocations
            # 3) the main product's own main/LT stock allocation
            side = self._ts_get_main_product_warehouse_side(line, main_entries, lt_entries, bnk_side=bnk_side)
            if side == 'split':
                for entry in reversed(self._ts_prepare_allocated_line_entries(line)):
                    if entry['side'] == 'lt':
                        lt_entries.insert(0, entry)
                    else:
                        main_entries.insert(0, entry)
                    main_product_sides.add(entry['side'])
                continue

            entry = self._ts_prepare_whole_line_entry(line, side=side)
            if side == 'lt':
                lt_entries.insert(0, entry)
            else:
                main_entries.insert(0, entry)
            main_product_sides.add(side)

        if not is_dxvt and main_product_sides:
            placeholder_lines = self.order_line.filtered(
                lambda l: self._ts_line_allowed_for_doc_type(l, doc_type='SO')
                and self._ts_is_lt_replacement_placeholder_line(l)
            )
            for line in placeholder_lines:
                if 'main' in main_product_sides:
                    main_entries.append(self._ts_prepare_whole_line_entry(line, side='main'))
                elif 'lt' in main_product_sides:
                    lt_entries.append(self._ts_prepare_whole_line_entry(line, side='lt'))

        return main_entries, lt_entries

    def _ts_call_api(self, route, payload, result_key_candidates=None):
        self.ensure_one()
        if not getattr(self, 'api_url', False):
            raise UserError(_('Missing api_url on sale.order.'))

        url = self.api_url + route
        headers = dict(getattr(self, 'api_headers', None) or {})
        safe_headers = {k: ('***' if 'auth' in k.lower() or 'token' in k.lower() else v) for k, v in headers.items()}
        is_dxvt_route = 'ITR' in route.upper()
        self._ts_post_sap_debug_persistent(
            'SAP REQUEST PAYLOAD - %s' % route,
            {
                'route': route,
                'url': url,
                'headers': safe_headers,
                'payload': payload,
            },
        )
        if is_dxvt_route:
            self._ts_post_sap_json_debug('DXVT REQUEST', {
                'route': route,
                'url': url,
                'headers': safe_headers,
                'payload': payload,
            })
        _logger.warning(
            '[LT_STOCK_DISPLAY] DOC API call start | SO=%s | method=POST | url=%s | route=%s | payload=%s | headers=%s',
            self.name or self.id, url, route, payload, safe_headers,
        )

        try:
            response = requests.request(
                'POST',
                url,
                headers=headers,
                json=payload,
                timeout=120,
            )
        except Exception as err:
            self._ts_log_sap_api_failure(
                route=route,
                url=url,
                headers=safe_headers,
                payload=payload,
                error=str(err),
            )
            _logger.exception('[LT_STOCK_DISPLAY] DOC API request failed | SO=%s | route=%s', self.name or self.id, route)
            if is_dxvt_route:
                self._ts_post_sap_json_debug('DXVT HTTP ERROR', {
                    'route': route,
                    'url': url,
                    'payload': payload,
                    'error': str(err),
                })
            raise UserError(_('SAP API call failed: %s %s') % (route, err))

        _logger.warning(
            '[LT_STOCK_DISPLAY] DOC raw response | SO=%s | route=%s | status=%s | reason=%s | text=%s',
            self.name or self.id, route, response.status_code, response.reason, response.text,
        )
        if response.status_code != 200:
            self._ts_log_sap_api_failure(
                route=route,
                url=url,
                headers=safe_headers,
                payload=payload,
                http_status=response.status_code,
                response=response.text,
                error=response.reason,
            )
            debug_title = 'DXVT RESPONSE ERROR' if is_dxvt_route else 'SO RESPONSE ERROR'
            self._ts_post_sap_json_debug(debug_title, {
                'route': route,
                'url': url,
                'payload': payload,
                'status_code': response.status_code,
                'reason': response.reason,
                'text': response.text,
            })
            raise UserError(_('SAP API call failed: %s %s') % (route, response.reason))

        try:
            data = response.json() or {}
        except Exception as err:
            self._ts_log_sap_api_failure(
                route=route,
                url=url,
                headers=safe_headers,
                payload=payload,
                http_status=response.status_code,
                response=response.text,
                error='Invalid JSON: %s' % err,
            )
            _logger.exception('[LT_STOCK_DISPLAY] DOC API invalid JSON | SO=%s | route=%s | text=%s',
                              self.name or self.id, route, response.text)
            if is_dxvt_route:
                self._ts_post_sap_json_debug('DXVT JSON PARSE ERROR', {
                    'route': route,
                    'url': url,
                    'payload': payload,
                    'text': response.text,
                    'error': str(err),
                })
            raise UserError(_('SAP API returned invalid JSON: %s %s') % (route, err))

        status = str(data.get('status', '')).strip().lower() if isinstance(data, dict) else ''
        if status == 'false':
            msg = data.get('msg') or data.get('message') or data
            self._ts_log_sap_api_failure(
                route=route,
                url=url,
                headers=safe_headers,
                payload=payload,
                http_status=response.status_code,
                response=data,
                error=msg,
            )
            debug_title = 'DXVT FAILED' if is_dxvt_route else 'SO FAILED'
            self._ts_post_sap_json_debug(debug_title, {
                'route': route,
                'url': url,
                'payload': payload,
                'response': data,
            })
            raise UserError(_('SAP API returned error for %s: %s') % (route, msg))

        result_key_candidates = result_key_candidates or [
            'docnumber', 'DocNumber', 'DocNum', 'docNum', 'DocEntry', 'docEntry', 'DocumentNumber'
        ]

        def _extract_from_dict(obj):
            if not isinstance(obj, dict):
                return False
            for key in result_key_candidates:
                value = obj.get(key)
                if value not in (None, '', False):
                    return value
            for key in ('result', 'data'):
                child = obj.get(key)
                if isinstance(child, dict):
                    nested = _extract_from_dict(child)
                    if nested:
                        return nested
            return False

        result = _extract_from_dict(data) or data
        if is_dxvt_route:
            self._ts_post_sap_json_debug('DXVT RESPONSE', {
                'route': route,
                'url': url,
                'payload': payload,
                'response': data,
                'result': result,
            })
        return result

    def _ts_log_sap_api_failure(self, route, url, headers, payload,
                                http_status=None, response=None, error=None):
        self.ensure_one()
        debug_data = {
            'so_id': self.id,
            'so_name': self.name,
            'route': route,
            'url': url,
            'headers': headers,
            'request_payload': payload,
            'http_status': http_status,
            'response': response,
            'error': error,
        }
        _logger.error(
            '[SAP_API_FAILED] %s',
            self._ts_json_dumps_for_debug(debug_data),
        )
        self._ts_post_sap_debug_persistent(
            'SAP API FAILED - RESPONSE',
            debug_data,
        )

    def _ts_post_sap_debug_persistent(self, title, debug_data):
        """Keep SAP request/debug details even when the business call rolls back."""
        self.ensure_one()
        try:
            with odoo.registry(self.env.cr.dbname).cursor() as cr:
                cr.execute("SET LOCAL lock_timeout = '3s'")
                debug_env = api.Environment(cr, odoo.SUPERUSER_ID, {})
                order = debug_env[self._name].browse(self.id).exists()
                if not order or not hasattr(order, 'message_post'):
                    return
                debug_json = self._ts_json_dumps_for_debug(debug_data)
                order.message_post(
                    body=Markup('<b>%s</b><pre>%s</pre>') % (title, debug_json),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                cr.commit()
        except Exception:
            _logger.exception(
                '[SAP_API_FAILED] Cannot persist chatter debug | SO=%s',
                self.name or self.id,
            )

    def _ts_json_dumps_for_debug(self, value):
        try:
            return json.dumps(value or {}, ensure_ascii=False, indent=2, default=str)
        except Exception:
            return str(value)

    def _ts_post_sap_json_debug(self, title, payload):
        self.ensure_one()
        if not hasattr(self, 'message_post'):
            return
        try:
            self.message_post(body='<b>%s</b><pre>%s</pre>' % (
                title,
                self._ts_json_dumps_for_debug(payload),
            ))
        except Exception:
            _logger.exception('[LT_SPLIT_DXVT] Failed to post debug message | SO=%s | title=%s', self.name or self.id, title)

    def _ts_prepare_doc_lines_payload(self, entries, include_price=False):
        self.ensure_one()
        tax_code = False
        if include_price and getattr(self, 'is_exchange_1_1', False):
            tax_code = (getattr(self, 'sap_tax_code', False) or 'SVN3').strip()
        payload_lines = []
        for entry in entries:
            line = entry['line']
            qty = self._float_or_zero(entry['quantity'])
            if qty <= 0:
                continue
            item_code = (
                (
                    self._get_line_item_code_for_sap(line)
                    if hasattr(self, '_get_line_item_code_for_sap')
                    else False
                )
                or getattr(getattr(line, 'product_template_id', False), 'default_code', False)
                or line.product_id.default_code
                or ''
            ).strip()
            if not item_code:
                continue
            payload_line = {
                'ItemCode': item_code,
                'Quantity': qty,
                'WhsCode': (entry.get('warehouse_code') or '').strip(),
            }
            if include_price and 'price_unit' in line._fields:
                discount_amount = self._float_or_zero(getattr(line, 'sap_discount_amount', 0.0))
                price_unit = self._float_or_zero(line.price_unit)
                payload_line.update({
                    'Price': price_unit - discount_amount,
                    'U_isDiscount': getattr(line, 'sap_is_discount', False) or '',
                    'U_WarrTime': getattr(line, 'sap_wmonth', 0) or 0,
                    'U_OrigiDiscPrcnt': self._float_or_zero(getattr(line, 'discount', 0.0)),
                    'U_OrigiPrice': price_unit,
                    'U_DiscAmt': discount_amount,
                })
            if tax_code:
                payload_line['TaxCode'] = tax_code
            payload_lines.append(payload_line)
        return payload_lines

    def _ts_bool_to_yn(self, value, true_value='Y', false_value='N'):
        return true_value if bool(value) else false_value

    def _ts_map_issue_invoice_value(self, value=None):
        raw = getattr(self, 'is_issue_invoice', False) if value is None else value
        if raw in (None, False, ''):
            return 'N'
        if raw is True:
            return 'Y'
        if isinstance(raw, str):
            normalized = raw.strip()
            upper = normalized.upper()
            if upper in {'Y', 'N', 'A', 'B', 'T', 'C'}:
                return upper
            lower = normalized.casefold()
            mapping = {
                'false': 'N',
                'true': 'Y',
                'không lấy hóa đơn': 'N',
                'khong lay hoa don': 'N',
                'phhđ ngay': 'Y',
                'phhđ sau': 'A',
                'giá có vat - không phhđ': 'B',
                'gia co vat - khong phhd': 'B',
                'phhđ sau bằng tay': 'T',
                'phhđ ngay bằng tay': 'C',
            }
            if lower in mapping:
                return mapping[lower]
        return 'Y' if bool(raw) else 'N'

    def _ts_safe_code(self, rec, attrs, default=''):
        if not rec:
            return default
        for attr in attrs:
            value = getattr(rec, attr, False)
            if value not in (None, False, ''):
                return value
        return default

    def _ts_prepare_so_payload(self, entries, line_key='Lines'):
        self.ensure_one()
        if not entries:
            return {}

        lines_payload = self._ts_prepare_doc_lines_payload(entries, include_price=True)
        if hasattr(self, 'prepare_sap_so_payload'):
            payload = dict(self.prepare_sap_so_payload() or {})
            payload.pop('Items' if line_key == 'Lines' else 'Lines', None)
            payload[line_key] = lines_payload
            return payload

        if hasattr(self, '_validate_exchange_sap_values'):
            self._validate_exchange_sap_values()

        invoice_partner = getattr(self, 'partner_invoice_id', False) or self.partner_id
        shipping_partner = getattr(self, 'partner_shipping_id', False) or self.partner_id

        today = fields.Date.context_today(self)
        filler_code = (entries[0].get('warehouse_code') or '').strip()

        card_code = self._ts_safe_code(self.partner_id, ['card_code', 'ref', 'CardCode'])
        secondary_card_code = self._ts_safe_code(shipping_partner, ['ref', 'CardCode', 'card_code'], card_code)
        serial_item_metadata = (
            self._get_serial_item_so_metadata()
            if hasattr(self, '_get_serial_item_so_metadata')
            else {}
        )
        slp_code = serial_item_metadata.get('SlpCode') or self._ts_safe_code(
            getattr(self, 'user_id', False), ['SlpCode', 'slp_code']
        )
        cntct_code = self._ts_safe_code(getattr(self, 'partner_id', False), ['CntctCode', 'cntct_code'])
        project_code = self._ts_safe_code(getattr(self, 'project_id', False), ['code', 'name'])
        trnsp_code = self._ts_safe_code(getattr(self, 'carrier_id', False), ['sap_code', 'code'])
        branch_code = self._ts_safe_code(getattr(getattr(self, 'user_id', False), 'branch_id', False), ['code'])
        store_code = (
            self._compute_store_for_sap(serial_item_metadata=serial_item_metadata)
            if hasattr(self, '_compute_store_for_sap')
            else branch_code or ''
        )
        sap_reason = getattr(self, 'sap_reason_id', False)
        reason_code = (sap_reason.code or '') if sap_reason else (getattr(self, 'reason', False) or '')
        issue_invoice = (
            self._get_sap_issue_invoice_for_payload()
            if hasattr(self, '_get_sap_issue_invoice_for_payload')
            else getattr(self, 'sap_is_issue_invoice', False) or getattr(self, 'is_issue_invoice', False)
        )
        voucher_type = getattr(self, 'sap_voucher_type', False) or self._ts_safe_code(
            getattr(self, 'voucher_type_id', False), ['code', 'name']
        )

        warehouse_note = get_sap_request_body_html(getattr(self, 'note', False) or '').strip()
        document_note = get_sap_request_body_html(
            getattr(self, 'document_note', False)
            or (
                self.ticket_id._build_document_note()
                if getattr(self, 'ticket_id', False) and hasattr(self.ticket_id, '_build_document_note')
                else ''
            )
            or ''
        ).strip()
        payload = {
            'CardCode': card_code,
            'U_CardCode2': secondary_card_code or card_code,
            'PostingDate': get_sap_request_body_date(fields.Date.context_today(self)),
            'DocDueDate': get_sap_request_body_date(
                getattr(self, 'commitment_date', False)
                or getattr(self, 'expected_date', False)
                or getattr(self, 'validity_date', False)
                or today
            ),
            'TaxDate': get_sap_request_body_date(fields.Date.context_today(self)),
            'Filler': filler_code,
            'ToWhsCode': '',
            'Comments': document_note,
            'U_NoteForAcc': document_note,
            'U_NoteForAll': document_note,
            'U_NoteForWhs': warehouse_note,
            'U_Store': store_code,
            'U_InvStore': store_code,
            'U_VoucherTypeID': voucher_type,
            'U_IsIssueInvoice': self._ts_map_issue_invoice_value(issue_invoice),
            'U_isInstall': get_sap_request_body_bool(getattr(self, 'sap_is_install', False)),
            'U_IsCOCQ': get_sap_request_body_bool(getattr(self, 'sap_is_cocq', False)),
            'U_IsSetup': get_sap_request_body_bool(getattr(self, 'sap_is_setup', False)),
            'SlpCode': slp_code,
            'TrnspCode': trnsp_code,
            'Project': project_code,
            'ShipToCode': self._ts_safe_code(shipping_partner, ['ref', 'ship_to_code', 'ShipToCode']),
            'PayToCode': self._ts_safe_code(invoice_partner, ['ref', 'pay_to_code', 'PayToCode']),
            'Address': getattr(shipping_partner, 'contact_address', False) or getattr(shipping_partner, 'street', False) or '',
            'Address2': (getattr(self, 'address2', False) or '').strip(),
            'U_Reasons': reason_code,
            'U_BusinessUnit': serial_item_metadata.get('U_BusinessUnit') or '',
            'CntctCode': cntct_code,
            'U_CarCodeCommission': self._ts_safe_code(getattr(self, 'commission_partner_id', False), ['ref', 'code']),
            'LicTradNum': getattr(invoice_partner, 'vat', False) or getattr(self.partner_id, 'vat', False) or '',
            'U_SONumberRef': self.name or '',
            'U_Compaign': '',
            'U_ExtCampaign': '',
            line_key: lines_payload,
        }
        return payload

    def _ts_get_dxvt_to_whs_code(self, entries):
        self.ensure_one()
        if hasattr(self, '_get_dxvt_target_warehouse_code'):
            target_code = (self._get_dxvt_target_warehouse_code() or '').strip()
            if target_code:
                return target_code
        candidates = [
            getattr(getattr(self, 'to_warehouse_id', False), 'code', False),
            getattr(getattr(self, 'warehouse_to_id', False), 'code', False),
            getattr(getattr(self, 'transfer_warehouse_id', False), 'code', False),
            getattr(getattr(self, 'receipt_warehouse_id', False), 'code', False),
            getattr(self, 'to_whs_code', False),
            getattr(self, 'to_whscode', False),
            getattr(self, 'to_whs', False),
        ]
        for code in candidates:
            code = (code or '').strip()
            if code:
                return code
        first_source = (entries and entries[0].get('warehouse_code') or '').strip()
        return first_source

    def _ts_prepare_dxvt_payload(self, entries):
        self.ensure_one()
        if not entries:
            return {}

        card_code = (
            getattr(getattr(self, 'partner_id', False), 'card_code', False)
            or getattr(getattr(self, 'partner_id', False), 'ref', False)
            or ''
        ).strip()
        if not card_code:
            raise UserError(_('Khách hàng trên SO chưa có CardCode nên không thể tạo ĐXVT.'))

        filler_code = (entries[0].get('warehouse_code') or '').strip()
        to_whs_code = self._ts_get_dxvt_to_whs_code(entries)
        document_note = get_sap_request_body_html(
            getattr(self, 'document_note', False)
            or (
                self.ticket_id._build_document_note()
                if getattr(self, 'ticket_id', False) and hasattr(self.ticket_id, '_build_document_note')
                else ''
            )
            or ''
        ).strip()
        warehouse_note = get_sap_request_body_html(
            getattr(self, 'note', False) or ''
        ).strip()
        today = fields.Date.context_today(self)
        action = getattr(getattr(self, 'ticket_id', False), 'service_action', '') or ''
        is_warranty = action in (
            'warranty_at_dat',
            'warranty_onsite',
            'warranty_at_dat_paid',
            'warranty_onsite_paid',
        )
        lines_payload = self._ts_prepare_doc_lines_payload(entries, include_price=False)
        payload = {
            'CardCode': card_code,
            'PostingDate': get_sap_request_body_date(fields.Date.context_today(self)),
            'DocDueDate': get_sap_request_body_date(
                getattr(self, 'commitment_date', False)
                or getattr(self, 'expected_date', False)
                or today
            ),
            'Filler': filler_code,
            'ToWhsCode': to_whs_code,
            'TaxDate': get_sap_request_body_date(fields.Date.context_today(self)),
            'Comments': document_note,
            'U_VoucherTypeID': '3130' if is_warranty else '3140',
            'U_Store': self._compute_store_for_sap() if hasattr(self, '_compute_store_for_sap') else '',
            'U_NoteForAll': document_note,
            'U_NoteForWhs': warehouse_note,
            'U_SONumberRef': self.name or '',
            'Items': lines_payload,
        }
        return payload

    def _ts_group_entries_by_warehouse(self, entries, doc_type='SO'):
        self.ensure_one()
        grouped = defaultdict(list)
        for entry in entries:
            source_wh = (entry.get('warehouse_code') or '').strip()
            if doc_type == 'DXVT':
                target_wh = self._ts_get_dxvt_to_whs_code([entry])
                key = (source_wh, target_wh)
            else:
                key = (source_wh, '')
            grouped[key].append(entry)
        return list(grouped.values())

    def _ts_set_doc_number(self, side, doc_num, doc_type='SO'):
        self.ensure_one()
        if not doc_num:
            return
        doc_str = str(doc_num)
        if doc_type == 'DXVT':
            if side == 'lt':
                self.ts_lt_dxvt_doc_number = doc_str
            else:
                self.ts_main_dxvt_doc_number = doc_str
                for fname in ('sap_dxvt_order_number', 'sap_itr_number', 'sap_dxvt_doc_number'):
                    if fname in self._fields:
                        try:
                            self[fname] = doc_str
                            break
                        except Exception:
                            continue
            return
        if side == 'lt':
            self.ts_lt_so_doc_number = doc_str
        else:
            self.ts_main_so_doc_number = doc_str
            for fname in ('sap_order_number', 'sap_so_number', 'sap_doc_number'):
                if fname in self._fields:
                    try:
                        self[fname] = doc_str
                        break
                    except Exception:
                        continue

    def _ts_get_existing_doc_number(self, side, doc_type='SO'):
        self.ensure_one()
        if doc_type == 'DXVT':
            candidates = (
                ('ts_lt_dxvt_doc_number',)
                if side == 'lt'
                else ('ts_main_dxvt_doc_number', 'sap_dxvt_order_number', 'sap_itr_number', 'sap_dxvt_doc_number')
            )
        else:
            candidates = (
                ('ts_lt_so_doc_number',)
                if side == 'lt'
                else ('ts_main_so_doc_number', 'sap_order_number', 'sap_so_number', 'sap_doc_number')
            )

        for fname in candidates:
            if fname not in self._fields:
                continue
            value = (self[fname] or '').strip()
            if value:
                return value
        return False

    def _ts_get_doc_state(self):
        self.ensure_one()
        try:
            state = json.loads(self.ts_split_sap_doc_state or '{}')
        except Exception:
            return {}
        return state if isinstance(state, dict) else {}

    def _ts_doc_group_key(self, entries, doc_type='SO'):
        self.ensure_one()
        if not entries:
            return 'empty'
        source_wh = (entries[0].get('warehouse_code') or '').strip()
        if doc_type == 'DXVT':
            target_wh = self._ts_get_dxvt_to_whs_code(entries)
            return '%s>%s' % (source_wh, (target_wh or '').strip())
        return source_wh or 'default'

    def _ts_get_existing_group_doc_number(self, side, group_key, doc_type='SO'):
        self.ensure_one()
        state = self._ts_get_doc_state()
        return (
            state.get(doc_type, {})
            .get(side, {})
            .get(group_key)
        ) or False

    def _ts_set_group_doc_number(self, side, group_key, doc_num, doc_type='SO'):
        self.ensure_one()
        if not group_key or not doc_num:
            return
        state = self._ts_get_doc_state()
        state.setdefault(doc_type, {}).setdefault(side, {})[group_key] = str(doc_num)
        self.ts_split_sap_doc_state = json.dumps(state, ensure_ascii=False, sort_keys=True)

    def _ts_persist_doc_number(self, side, doc_num, doc_type='SO', group_key=False):
        self.ensure_one()
        if not doc_num:
            return
        doc_str = str(doc_num)
        self._ts_set_doc_number(side, doc_str, doc_type=doc_type)
        if group_key:
            self._ts_set_group_doc_number(side, group_key, doc_str, doc_type=doc_type)
        try:
            with odoo.registry(self.env.cr.dbname).cursor() as cr:
                cr.execute("SET LOCAL lock_timeout = '3s'")
                persist_env = api.Environment(cr, odoo.SUPERUSER_ID, {})
                order = persist_env[self._name].browse(self.id).exists()
                if not order:
                    return
                order._ts_set_doc_number(side, doc_str, doc_type=doc_type)
                if group_key:
                    order._ts_set_group_doc_number(side, group_key, doc_str, doc_type=doc_type)
                if hasattr(order, 'message_post'):
                    side_label = 'LT' if side == 'lt' else 'Main'
                    label = 'DXVT' if doc_type == 'DXVT' else 'SO'
                    order.message_post(
                        body=_('%s %s created in SAP: %s') % (side_label, label, doc_str),
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
                cr.commit()
        except Exception:
            _logger.exception(
                '[LT_SPLIT_%s] Failed to persist successful doc number | SO=%s | side=%s | doc=%s',
                doc_type,
                self.name or self.id,
                side,
                doc_str,
            )

    def _ts_log_doc_result(self, main_docs, lt_docs, doc_type='SO'):
        self.ensure_one()
        main_docs = [str(x) for x in (main_docs or []) if x not in (None, False, '')]
        lt_docs = [str(x) for x in (lt_docs or []) if x not in (None, False, '')]
        parts = []
        label = 'DXVT' if doc_type == 'DXVT' else 'SO'
        if main_docs:
            parts.append(_('Main %s: %s') % (label, ', '.join(main_docs)))
        if lt_docs:
            parts.append(_('LT %s: %s') % (label, ', '.join(lt_docs)))
        note = ' | '.join(parts)
        if doc_type == 'DXVT':
            self.ts_split_dxvt_note = note
        else:
            self.ts_split_doc_note = note
        if note and hasattr(self, 'message_post'):
            try:
                self.message_post(body=note)
            except Exception:
                _logger.exception('[LT_SPLIT_%s] Failed to post message for %s', label, self.name or self.id)

    def _ts_create_docs_for_entries(self, entries, doc_type='SO', side='main'):
        self.ensure_one()
        if not entries:
            return []
        api_route = self.SO_MAIN_API
        if doc_type == 'DXVT':
            api_route = self.DXVT_LT_API if side == 'lt' else self.DXVT_MAIN_API
        else:
            api_route = self.SO_LT_API if side == 'lt' else self.SO_MAIN_API

        docs = []
        entry_groups = self._ts_group_entries_by_warehouse(entries, doc_type=doc_type)
        side_existing_doc = self._ts_get_existing_doc_number(side, doc_type=doc_type) if len(entry_groups) == 1 else False
        for group_entries in entry_groups:
            group_key = self._ts_doc_group_key(group_entries, doc_type=doc_type)
            existing_doc = (
                self._ts_get_existing_group_doc_number(side, group_key, doc_type=doc_type)
                or side_existing_doc
            )
            if existing_doc:
                _logger.info(
                    '[LT_SPLIT_%s] skip %s API because group doc already exists | SO=%s | group=%s | doc=%s',
                    doc_type,
                    side,
                    self.name or self.id,
                    group_key,
                    existing_doc,
                )
                docs.append(str(existing_doc))
                continue
            if doc_type == 'DXVT':
                payload = self._ts_prepare_dxvt_payload(group_entries)
                _logger.info('[LT_SPLIT_DXVT][%s_PAYLOAD] so=%s payload=%s', side.upper(), self.name or self.id, payload)
            else:
                payload = self._ts_prepare_so_payload(group_entries, line_key='Lines')
                _logger.info('[LT_SPLIT_SO][%s_PAYLOAD] so=%s payload=%s', side.upper(), self.name or self.id, payload)
            payload_lines = payload.get('Lines') or payload.get('Items')
            if not payload_lines:
                continue
            doc = self._ts_call_api(api_route, payload)
            if doc:
                doc = str(doc)
                docs.append(doc)
                self._ts_persist_doc_number(side, doc, doc_type=doc_type, group_key=group_key)
        return docs

    def _ts_prepare_batch_side_entries(self, orders):
        main_entries = []
        lt_entries = []
        for order in orders:
            if not order._use_lt_stock_display_bridge():
                continue
            order._ts_prepare_split_allocations()
            order_main_entries, order_lt_entries = order._ts_selected_lines_by_side(doc_type='SO')
            for entry in order_main_entries:
                entry['order'] = order
                main_entries.append(entry)
            for entry in order_lt_entries:
                entry['order'] = order
                lt_entries.append(entry)
            _logger.info(
                '[LT_SPLIT_SO_BATCH] selected entries | SO=%s | main=%s | lt=%s',
                order.name or order.id,
                [
                    {
                        'line_id': item['line'].id,
                        'item': item['line'].product_id.default_code,
                        'qty': item['quantity'],
                        'wh': item.get('warehouse_code'),
                        'alloc': item.get('allocation'),
                    }
                    for item in order_main_entries
                ],
                [
                    {
                        'line_id': item['line'].id,
                        'item': item['line'].product_id.default_code,
                        'qty': item['quantity'],
                        'wh': item.get('warehouse_code'),
                        'alloc': item.get('allocation'),
                    }
                    for item in order_lt_entries
                ],
            )
        return main_entries, lt_entries

    def _ts_prepare_batch_so_lines_payload(self, entries):
        payload_lines = []
        for entry in entries:
            line = entry['line']
            order = entry.get('order') or line.order_id
            qty = order._float_or_zero(entry.get('quantity'))
            if qty <= 0:
                continue
            item_code = (
                (
                    order._get_line_item_code_for_sap(line)
                    if hasattr(order, '_get_line_item_code_for_sap')
                    else False
                )
                or getattr(getattr(line, 'product_template_id', False), 'default_code', False)
                or line.product_id.default_code
                or ''
            ).strip()
            if not item_code:
                continue

            discount_amount = order._float_or_zero(getattr(line, 'sap_discount_amount', 0.0))
            price_unit = order._float_or_zero(getattr(line, 'price_unit', 0.0))
            line_payload = {
                'ItemCode': item_code,
                'Quantity': qty,
                'Price': price_unit - discount_amount,
                'WhsCode': (entry.get('warehouse_code') or '').strip(),
                'U_isDiscount': getattr(line, 'sap_is_discount', False) or '',
                'U_WarrTime': getattr(line, 'sap_wmonth', 0) or 0,
                'U_OrigiDiscPrcnt': order._float_or_zero(getattr(line, 'discount', 0.0)),
                'U_OrigiPrice': price_unit,
                'U_DiscAmt': discount_amount,
            }
            if hasattr(order, '_get_sap_tax_code_for_payload'):
                tax_code = order._get_sap_tax_code_for_payload()
                if tax_code:
                    line_payload['TaxCode'] = tax_code
            payload_lines.append(line_payload)
        return payload_lines

    def _ts_prepare_batch_so_payload_for_entries(self, orders, entries):
        if not entries:
            return {}
        base_payload = dict(orders._prepare_sap_so_batch_payload() or {})
        base_payload['Lines'] = self._ts_prepare_batch_so_lines_payload(entries)
        return base_payload

    def _ts_action_create_sap_so_batch_bridge(self, original_action_create_sap_so_batch):
        if not self:
            return original_action_create_sap_so_batch(self)

        orders = self.filtered(lambda order: order.wf_external_id == 'workflow_1')
        orders = orders.filtered(lambda order: not (order.sap_status or '').strip())
        if not orders:
            return original_action_create_sap_so_batch(self)

        if not all(order._use_lt_stock_display_bridge() for order in orders):
            return original_action_create_sap_so_batch(self)

        main_entries, lt_entries = self._ts_prepare_batch_side_entries(orders)
        if not lt_entries:
            _logger.info(
                '[LT_SPLIT_SO_BATCH] no LT entries, fallback original batch | orders=%s',
                orders.ids,
            )
            return original_action_create_sap_so_batch(self)

        main_order = orders[0]
        main_docs = []
        lt_docs = []

        if main_entries:
            existing_main_docs = list(dict.fromkeys(
                doc for doc in (
                    order._ts_get_existing_doc_number('main', doc_type='SO')
                    for order in orders
                ) if doc
            ))
            if existing_main_docs:
                main_docs = existing_main_docs
                _logger.info(
                    '[LT_SPLIT_SO_BATCH] skip MAIN API because doc already exists | orders=%s | docs=%s',
                    orders.ids,
                    main_docs,
                )
            else:
                payload = main_order._ts_prepare_batch_so_payload_for_entries(orders, main_entries)
                if payload.get('Lines'):
                    _logger.info(
                        '[LT_SPLIT_SO_BATCH][MAIN_PAYLOAD] orders=%s payload=%s',
                        orders.ids,
                        payload,
                    )
                    doc = main_order._ts_call_api(main_order.SO_MAIN_API, payload)
                    if doc:
                        doc = str(doc)
                        main_docs.append(doc)
                        for order in orders:
                            order._ts_persist_doc_number('main', doc, doc_type='SO')

        if lt_entries:
            existing_lt_docs = list(dict.fromkeys(
                doc for doc in (
                    order._ts_get_existing_doc_number('lt', doc_type='SO')
                    for order in orders
                ) if doc
            ))
            if existing_lt_docs:
                lt_docs = existing_lt_docs
                _logger.info(
                    '[LT_SPLIT_SO_BATCH] skip LT API because doc already exists | orders=%s | docs=%s',
                    orders.ids,
                    lt_docs,
                )
            else:
                payload = main_order._ts_prepare_batch_so_payload_for_entries(orders, lt_entries)
                if payload.get('Lines'):
                    _logger.info(
                        '[LT_SPLIT_SO_BATCH][LT_PAYLOAD] orders=%s payload=%s',
                        orders.ids,
                        payload,
                    )
                    doc = main_order._ts_call_api(main_order.SO_LT_API, payload)
                    if doc:
                        doc = str(doc)
                        lt_docs.append(doc)
                        for order in orders:
                            order._ts_persist_doc_number('lt', doc, doc_type='SO')

        if not main_docs and not lt_docs:
            raise UserError(_('No SAP SO document was created for the batch.'))

        result_parts = []
        if main_docs:
            result_parts.append('Main: %s' % ', '.join(main_docs))
        if lt_docs:
            result_parts.append('LT: %s' % ', '.join(lt_docs))
        result = ' | '.join(result_parts)

        for index, order in enumerate(orders):
            vals = dict(order._prepare_confirmation_values()) if hasattr(order, '_prepare_confirmation_values') else {}
            if 'sap_status' in order._fields:
                vals['sap_status'] = result
            if index == 0 and main_docs:
                vals['name'] = main_docs[0]
            order.write(vals)
            order._ts_log_doc_result(main_docs, lt_docs, doc_type='SO')
            if main_docs:
                order._ts_set_doc_number('main', main_docs[0], doc_type='SO')
            if lt_docs:
                order._ts_set_doc_number('lt', lt_docs[0], doc_type='SO')

        return False

    def _ts_create_sap_doc_bridge(self, original_create_sap_doc, doc_type='SO'):
        self.ensure_one()
        normalized_type = (doc_type or 'SO').upper()
        is_dxvt = normalized_type in ('DXVT', 'ITR', 'INTERNAL_TRANSFER')

        if not self._use_lt_stock_display_bridge():
            return original_create_sap_doc(self, doc_type=doc_type)

        if not is_dxvt and 'sap_is_create_so' in self._fields and not self.sap_is_create_so:
            return original_create_sap_doc(self, doc_type=doc_type)

        self._ts_prepare_split_allocations()
        bridge_doc_type = 'DXVT' if is_dxvt else 'SO'
        main_entries, lt_entries = self._ts_selected_lines_by_side(doc_type=bridge_doc_type)

        main_groups = self._ts_group_entries_by_warehouse(main_entries, doc_type=bridge_doc_type)

        # Pure main flow: preserve original behavior
        if not lt_entries and not (is_dxvt and len(main_groups) > 1):
            return original_create_sap_doc(self, doc_type=doc_type)

        main_docs = []
        lt_docs = []

        if main_entries:
            main_docs = self._ts_create_docs_for_entries(main_entries, doc_type='DXVT' if is_dxvt else 'SO', side='main')
            if main_docs:
                self._ts_set_doc_number('main', main_docs[0], doc_type='DXVT' if is_dxvt else 'SO')

        if lt_entries:
            lt_docs = self._ts_create_docs_for_entries(lt_entries, doc_type='DXVT' if is_dxvt else 'SO', side='lt')
            if lt_docs:
                self._ts_set_doc_number('lt', lt_docs[0], doc_type='DXVT' if is_dxvt else 'SO')

        if not main_docs and not lt_docs:
            raise UserError(_('No SAP %s document was created.') % ('DXVT' if is_dxvt else 'SO'))

        self._ts_log_doc_result(main_docs, lt_docs, doc_type='DXVT' if is_dxvt else 'SO')
        all_docs = main_docs + ['LT:%s' % x for x in lt_docs]
        result = ' | '.join(all_docs)
        if not is_dxvt and hasattr(self, '_prepare_confirmation_values'):
            vals = dict(self._prepare_confirmation_values())
            if 'sap_status' in self._fields:
                vals['sap_status'] = result
            if main_docs:
                vals['name'] = main_docs[0]
            self.write(vals)
        return result
