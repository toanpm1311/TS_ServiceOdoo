import logging
import requests

from odoo import _, api, fields, models
from odoo.osv import expression


_logger = logging.getLogger(__name__)


class TicketHelpdesk(models.Model):
    _inherit = 'ticket.helpdesk'

    bnk_replacement_so_status = fields.Char(string='SOStatus', copy=False, readonly=True)
    bnk_replacement_serial_sync_at = fields.Datetime(string='BnK Serial Sync At', copy=False, readonly=True)
    bnk_replacement_serial_sync_note = fields.Char(string='BnK Serial Sync Note', copy=False, readonly=True)
    bnk_replacement_sync_done = fields.Boolean(string='BnK Serial Sync Done', copy=False, readonly=True)

    def action_sync_sap_customer_data(self):
        self.ensure_one()
        return self.env['res.partner'].action_sync_sap_customer_data()

    def _bnk_replacement_check_routes(self):
        return (
            '/CheckSeriBaoHanhTuSoLenh',
            '/CheckSeriBaoHanhTuSoLenhLT',
        )

    def _bnk_replacement_terminal_statuses(self):
        return {
            'CANCELLED',
            'CANCELED',
            'DUNGXULY',
            'DUNG_XU_LY',
            'STOPPED',
        }

    def _bnk_is_replacement_terminal_status(self, so_status):
        normalized_status = str(so_status or '').strip().upper().replace(' ', '').replace('-', '_')
        return normalized_status in self._bnk_replacement_terminal_statuses()

    def _bnk_get_base_url(self):
        ICP = self.env['ir.config_parameter'].sudo()
        api_base_url = (ICP.get_param('dat_bnk.bnk_api_url') or '').strip()
        if not api_base_url:
            api_base_url = 'https://api-dat.datgroup.com.vn/BnK'
        return api_base_url.rstrip('/')

    def _bnk_get_headers(self):
        try:
            headers = dict(self._get_sap_headers_safe() or {})
        except Exception:
            headers = dict(self.env['res.config.settings'].sudo().get_sap_headers() or {})
        headers.setdefault('Content-Type', 'application/json')
        return headers

    def _bnk_get_replacement_order_numbers(self):
        self.ensure_one()
        order_numbers = []
        invalid_values = {
            'OPEN',
            'CLOSED',
            'CANCELLED',
            'CANCELED',
            'NOT_FOUND',
        }

        def add_order_number(raw_value):
            for value in str(raw_value or '').replace(';', ',').replace('\n', ',').split(','):
                value = value.strip()
                if ':' in value:
                    value = value.split(':', 1)[1].strip()
                # U_S1No may be an SAP DocNum or the HCM reference stored on
                # the SAP document. ``sap_status`` is also (incorrectly) used
                # for OPEN/CLOSED, so only reject known status values.
                if (
                    value
                    and value.upper() not in invalid_values
                    and value not in order_numbers
                ):
                    order_numbers.append(value)

        for order in self.sale_order_ids:
            # create_sap_doc stores the SAP DocNum in both name and sap_status.
            # The status cron can later overwrite sap_status; name remains the
            # reliable fallback for already-created SAP orders.
            add_order_number(getattr(order, 'name', False))
            add_order_number(getattr(order, 'sap_status', False))
            add_order_number(getattr(order, 'sap_sale_order_number', False))
            add_order_number(getattr(order, 'sap_dxvt_order_number', False))
        add_order_number(self.sap_sale_order_number)
        add_order_number(self.sap_dxvt_order_number)

        return order_numbers

    def _bnk_call_replacement_serial_status(self, order_number):
        self.ensure_one()
        headers = self._bnk_get_headers()
        base_url = self._bnk_get_base_url()
        payload = {'U_S1No': order_number}
        last_result = {}
        best_result = {}

        for route in self._bnk_replacement_check_routes():
            url = '%s%s' % (base_url, route)
            _logger.info(
                'BnK replacement serial check request | ticket=%s | url=%s | json=%s',
                self.name,
                url,
                payload,
            )
            response = requests.get(url, headers=headers, json=payload, timeout=30)
            response_text = response.text or ''
            _logger.info(
                'BnK replacement serial check response | ticket=%s | url=%s | status=%s | body=%s',
                self.name,
                url,
                response.status_code,
                response_text[:1000],
            )
            if response.status_code != 200:
                continue
            try:
                response_json = response.json() if response_text else {}
            except ValueError:
                _logger.warning(
                    'BnK replacement serial check returned invalid JSON | ticket=%s | url=%s | body=%s',
                    self.name,
                    url,
                    response_text[:1000],
                )
                continue

            if isinstance(response_json, list):
                result = response_json
                response_status = False
            elif isinstance(response_json, dict):
                result = response_json.get('result') or response_json.get('data') or []
                response_status = response_json.get('SOStatus')
            else:
                result = []
                response_status = False
            rows = result if isinstance(result, list) else [result]
            row = next((dict(item or {}) for item in rows if isinstance(item, dict)), {})
            so_status = row.get('SOStatus') or response_status
            serial_number = str(row.get('SerialNumber') or '').strip()
            last_result = {
                'route': route,
                'response': response_json,
                'so_status': so_status,
                'serial_number': serial_number,
            }
            if serial_number:
                return last_result
            if so_status and (not best_result or not self._bnk_is_replacement_terminal_status(so_status)):
                best_result = last_result

        return best_result or last_result

    def _bnk_prepare_replacement_lot_values(self, serial_number):
        self.ensure_one()
        old_lot = self.stock_lot_id
        owner = self.owner_id or self.customer_id
        buyer = self.customer_id or owner
        values = {
            'name': serial_number,
        }
        if old_lot and old_lot.product_id:
            values['product_id'] = old_lot.product_id.id
        if old_lot and old_lot.company_id:
            values['company_id'] = old_lot.company_id.id
        if old_lot:
            values['product_qty'] = old_lot.product_qty
        if buyer:
            values['buyer_id'] = buyer.id
        if owner:
            values['owner_id'] = owner.id
        if old_lot and old_lot.warranty_start_date:
            values['warranty_start_date'] = old_lot.warranty_start_date
        if old_lot and old_lot.warranty_month:
            values['warranty_month'] = old_lot.warranty_month
        return values

    def _bnk_apply_replacement_serial_result(self, serial_number, so_status=None, source=None):
        self.ensure_one()
        serial_number = (serial_number or '').strip()
        if not serial_number:
            return False

        StockLot = self.env['stock.lot'].sudo()
        new_lot = StockLot.search([('name', '=', serial_number)], limit=1)
        lot_values = self._bnk_prepare_replacement_lot_values(serial_number)
        if new_lot:
            lot_values.pop('name', None)
            new_lot.write(lot_values)
        else:
            new_lot = StockLot.create(lot_values)

        old_lot = self.stock_lot_id.sudo()
        if old_lot and 'replaced_by' in old_lot._fields:
            old_lot.write({'replaced_by': new_lot.id})

        ticket_values = {
            'replace_serial_number': serial_number,
            'bnk_replacement_so_status': so_status or False,
            'bnk_replacement_serial_sync_at': fields.Datetime.now(),
            'bnk_replacement_serial_sync_note': source or '',
            'bnk_replacement_sync_done': True,
        }
        if 'new_stock_lot_id' in self._fields:
            ticket_values['new_stock_lot_id'] = new_lot.id
        if old_lot and old_lot.warranty_start_date and 'warranty_start_date' in self._fields:
            ticket_values['warranty_start_date'] = old_lot.warranty_start_date
        if old_lot and old_lot.warranty_end_date and 'warranty_end_date' in self._fields:
            ticket_values['warranty_end_date'] = old_lot.warranty_end_date
        if 'ts_serial_synced' in self._fields:
            ticket_values['ts_serial_synced'] = True
        if 'ts_last_serial_sync_at' in self._fields:
            ticket_values['ts_last_serial_sync_at'] = fields.Datetime.now()
        if 'ts_last_serial_sync_note' in self._fields:
            ticket_values['ts_last_serial_sync_note'] = source or ''
        self.write(ticket_values)
        self.message_post(body=_(
            'Updated replacement serial from BnK: %(serial)s. SOStatus: %(status)s.'
        ) % {
            'serial': serial_number,
            'status': so_status or '-',
        })
        return True

    def _bnk_sync_replacement_serial(self):
        self.ensure_one()
        order_numbers = self._bnk_get_replacement_order_numbers()
        if not order_numbers:
            _logger.info(
                'BnK replacement serial sync skipped: no SAP DocNum | ticket=%s',
                self.name,
            )
            return False
        for order_number in order_numbers:
            result = self._bnk_call_replacement_serial_status(order_number)
            so_status = result.get('so_status')
            serial_number = result.get('serial_number')
            route = result.get('route') or ''
            note = '%s U_S1No=%s' % (route, order_number)
            self.write({
                'bnk_replacement_so_status': so_status or False,
                'bnk_replacement_serial_sync_at': fields.Datetime.now(),
                'bnk_replacement_serial_sync_note': note,
                'bnk_replacement_sync_done': bool(self._bnk_is_replacement_terminal_status(so_status)),
            })
            if serial_number:
                return self._bnk_apply_replacement_serial_result(
                    serial_number,
                    so_status=so_status,
                    source=note,
                )
        return False

    @api.model
    def _bnk_replacement_candidate_domain(self):
        replacement_domain = expression.OR([
            [('is_exchange_1_1', '=', True)],
            [('sale_order_ids.is_exchange_1_1', '=', True)],
            [('warranty_service_type', '=', 'replace')],
            [('sap_reason_id.name', 'ilike', '1 đổi 1')],
            [('sale_order_ids.sap_reason_id.name', 'ilike', '1 đổi 1')],
            [('product_error_note', 'ilike', 'đổi mới')],
            [('product_error_note', 'ilike', 'doi moi')],
            [('description', 'ilike', 'đổi mới')],
            [('description', 'ilike', 'doi moi')],
            [('note_SO', 'ilike', 'đổi mới')],
            [('note_SO', 'ilike', 'doi moi')],
        ])
        reference_domain = expression.OR([
            [('sap_sale_order_number', '!=', False)],
            [('sap_dxvt_order_number', '!=', False)],
            [('sale_order_ids', '!=', False)],
        ])
        return expression.AND([
            replacement_domain,
            reference_domain,
        ])

    @api.model
    def cron_sync_bnk_replacement_serials(self, limit=100):
        self = self.sudo()
        domain = self._bnk_replacement_candidate_domain()
        limit = max(int(limit or 0), 1)

        # Do not repeatedly consume the same first 100 records. New/untried
        # tickets are checked first, then the least-recently checked tickets.
        unchecked_domain = expression.AND([
            domain,
            [('bnk_replacement_serial_sync_at', '=', False)],
        ])
        tickets = self.search(unchecked_domain, limit=limit, order='id desc')
        remaining = limit - len(tickets)
        if remaining:
            retry_domain = expression.AND([
                domain,
                [('bnk_replacement_serial_sync_at', '!=', False)],
            ])
            tickets |= self.search(
                retry_domain,
                limit=remaining,
                order='bnk_replacement_serial_sync_at asc, id desc',
            )
        _logger.info(
            'BnK replacement serial cron selected | count=%s | tickets=%s',
            len(tickets),
            ', '.join(tickets.mapped('name')),
        )
        synced = 0
        for ticket in tickets:
            try:
                with self.env.cr.savepoint():
                    if ticket._bnk_sync_replacement_serial():
                        synced += 1
            except Exception as error:
                _logger.exception(
                    'BnK replacement serial sync failed | ticket=%s | error=%s',
                    ticket.display_name,
                    error,
                )
                ticket.write({
                    'bnk_replacement_serial_sync_at': fields.Datetime.now(),
                    'bnk_replacement_serial_sync_note': str(error)[:255],
                })
        _logger.info(
            'BnK replacement serial cron finished | checked=%s | synced=%s',
            len(tickets),
            synced,
        )
        return True
