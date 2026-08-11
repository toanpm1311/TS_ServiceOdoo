import logging
from datetime import datetime
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CreateSerialWizard(models.TransientModel):
    _name = "create.serial.wizard"
    _inherit = ['abstract.sync.sap']
    _description = "Create Serial Wizard"

    sync_type = fields.Selection([
        ('partner', 'Theo khách hàng'),
        ('serial', 'Theo số serial'),
    ], string="Chế độ đồng bộ", default='serial', required=True)

    partner_ids = fields.Many2many(
        'res.partner', string='Khách hàng cần đồng bộ',
        help="Chỉ dùng khi chọn chế độ Theo khách hàng",
    )
    serial_number = fields.Char(
        string='Số Serial',
        help="Nhập số serial để đồng bộ (chỉ dùng khi chọn chế độ Theo số serial)",
    )

    def action_sync_serial_item(self):
        try:
            return self._sync_serial_items()
        except Exception as e:
            return self._show_reload_notification('danger', str(e))

    def _sync_serial_items(self):
        error_groups = {}

        if self.sync_type == 'partner':
            partners = self._validate_and_collect_partners(error_groups)
            for card_code, card_name in partners:
                try:
                    items = self._fetch_serial_items(card_code=card_code, card_name=card_name,
                                                     error_groups=error_groups)
                    for item in items or []:
                        self._process_serial_item(item, card_name, error_groups)
                except Exception as e:
                    self._add_error("Lỗi không xác định", f"{card_name} – {e}", error_groups)

        else:  # sync_type == 'serial'
            serial_number = (self.serial_number or '').strip()
            if not serial_number:
                raise UserError("Vui lòng nhập số serial để đồng bộ.")
            self.serial_number = serial_number
            existing_lot = self.env['stock.lot'].search([('name', '=', serial_number)], limit=1)
            if existing_lot:
                return self._show_notification(
                    'success',
                    _("Serial %(serial)s đã có trong hệ thống.") % {'serial': serial_number},
                    soft_reload=True,
                )
            try:
                items = self._fetch_serial_items(card_code='', card_name='', error_groups=error_groups,
                                                 serial_number=serial_number)
                for item in items or []:
                    self._process_serial_item(item, serial_number, error_groups, serial_number=serial_number)
            except Exception as e:
                self._add_error("Lỗi không xác định", f"{serial_number} – {e}", error_groups)
        return self._notify_by_errors(error_groups)

    def _validate_and_collect_partners(self, error_groups):
        self.ensure_one()
        if self.sync_type != 'partner':
            return []

        if not self.partner_ids:
            raise UserError("Vui lòng chọn khách hàng.")

        partners, missing = [], []
        for partner in self.partner_ids:
            (partners if partner.card_code else missing).append(
                (partner.card_code, partner.display_name) if partner.card_code else partner.name)

        for missing_item in missing:
            self._add_error("Các khách hàng sau không có mã cardcode:", missing_item, error_groups)

        return partners

    def _fetch_serial_items(self, card_code, card_name, error_groups, serial_number=None):
        payload = {
            'CardCode': '' if serial_number else card_code,
            'SerialNumber': serial_number or ""
        }
        response = self.api_method(
            self.api_url + '/SerialItem',
            headers=self.api_headers,
            json=payload,
        )
        if not response.ok:
            self._add_error("Lỗi gọi API SerialItem", card_name, error_groups)
            return None
        items = self._extract_serial_items(response.json())
        if serial_number and not items:
            items = self._fetch_serial_number_items(serial_number)
        if card_name and not items:
            self._add_error("Không có dữ liệu API trả về cho các khách hàng", card_name, error_groups)
        elif serial_number and not items:
            self._add_error("Không có dữ liệu API trả về cho Serial Number", serial_number, error_groups)
        return items

    def _fetch_serial_number_items(self, serial_number):
        response = self.api_method(
            self.api_url + '/SerialNumber',
            headers=self.api_headers,
            json={
                'SerialNumber': serial_number,
                'PageNumber': 1,
                'PageSize': 100,
            },
        )
        if not response.ok:
            return []
        return self._extract_serial_items(response.json())

    def _extract_serial_items(self, response_json):
        result = (response_json or {}).get('result') or {}
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            if isinstance(result.get('Items'), list):
                return result.get('Items')
            if result.get('SerialNumber'):
                return [result]
        return []

    def _process_serial_item(self, item, card_name, error_groups, serial_number=None):
        if not serial_number:
            serial_number = item.get('SerialNumber')
        if card_name and not self._check_and_log(serial_number, error_groups,
                                                 "Không có serial number cho các khách hàng", card_name):
            return
        lot = self.env['stock.lot'].search([('name', '=', serial_number)], limit=1)

        product = self.env['stock.lot']._find_product_by_item_code(item.get('ItemCode'))
        if not product and lot:
            product = lot.product_id
        if not product:
            product = self.env['stock.lot']._get_or_create_product_for_serial(item, serial_number)
        if not self._check_and_log(product, error_groups,
                                   "Không có product tương ứng với serial number", serial_number):
            return
        buyer = self._search_and_check('res.partner', [('card_code', '=', item.get('BuyerCode'))],
                                       "Không có khách hàng với mã serial number", serial_number, error_groups)
        owner_code = item.get('OwnerCode') or item.get('BuyerCode')
        owner = buyer if owner_code == item.get('BuyerCode') else self._search_and_check(
            'res.partner', [('card_code', '=', owner_code)],
            "Không có người sở hữu với mã serial number", serial_number, error_groups)

        if not product or not buyer or not owner:
            return

        employee = self.env['hr.employee'].search([('sap_slp_code', '=', item.get('SlpCode'))], limit=1) if item.get(
            'SlpCode') not in (None, '', 'null', False) else False
        self._upsert_stock_lot(item, product, buyer, owner, employee, lot)

    def _search_and_check(self, model, domain, error_key, error_value, error_groups):
        record = self.env[model].search(domain, limit=1)
        return record if self._check_and_log(record, error_groups, error_key, error_value) else None

    def _check_and_log(self, condition, error_groups, error_key, error_value):
        if not condition:
            self._add_error(error_key, error_value, error_groups)
            return False
        return True

    def _add_error(self, key, value, error_groups):
        error_groups.setdefault(key, []).append(value)

    def _upsert_stock_lot(self, item, product, buyer, owner, employee, lot=False):
        vals = {
            'product_id': product.id,
            'warranty_start_date': self._parse_date(item.get('DeliveryDate')),
            'warranty_month': int(item.get('WarrantyMonth') or 0),
            'buyer_id': buyer.id,
            'owner_id': owner.id,
            'saleperson_id': employee.id if employee else False,
        }
        if lot:
            lot.write(vals)
            return lot
        vals.update({
            'name': item.get('SerialNumber'),
            'note': f"Import từ API ngày {fields.Date.today()}",
        })
        return self.env['stock.lot'].create(vals)

    def _parse_date(self, value):
        if not value:
            return False
        try:
            return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            try:
                return datetime.fromisoformat(value.rstrip("Z"))
            except Exception as e:
                _logger.warning(f"Lỗi parse date: {value} - {e}")
                return False

    def _format_errors(self, error_groups):
        return [f"{k}:\n" + "\n".join(f"- {v}" for v in vs) for k, vs in error_groups.items()]

    def _notify_by_errors(self, error_groups):
        errors = self._format_errors(error_groups)
        return self._show_notification('warning' if errors else 'success',
                                       "\n".join(errors) if errors else 'Đồng bộ SerialNumber thành công',
                                       soft_reload=True)

    def _show_notification(self, type, message, soft_reload=False):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': type,
                'sticky': False,
                'message': message,
                **({'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}} if soft_reload else {}),
            },
        }

    def _show_reload_notification(self, type, message):
        return self._show_notification(type, message, soft_reload=False) | {
            'params': {
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _('Create Serial Wizard'),
                    'res_model': self._name,
                    'res_id': False,
                    'view_mode': 'form',
                    'view_type': 'form',
                    'views': [[False, 'form']],
                    'target': 'new',
                    'context': dict(self.env.context, **self._get_default_context_from_self()),
                }
            }
        }

    def _get_default_context_from_self(self, exclude_fields=None):
        context = {}
        exclude_fields = set(exclude_fields or [])
        for fname, field in self._fields.items():
            if fname in exclude_fields:
                continue
            try:
                val = getattr(self, fname)
                if isinstance(val, models.BaseModel) and field.type == 'many2one':
                    context[f'default_{fname}'] = val.id if val else False
                elif isinstance(val, models.Model) and field.type in ('many2many', 'one2many'):
                    context[f'default_{fname}'] = [(6, 0, val.ids)]
                else:
                    context[f'default_{fname}'] = val
            except Exception as e:
                _logger.warning(f"Skipped field '{fname}' due to error: {e}")
        return context
