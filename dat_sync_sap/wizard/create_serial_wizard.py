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
        ('existing', 'Các serial hiện có (theo batch)'),
    ], string="Chế độ đồng bộ", default='serial', required=True)

    partner_ids = fields.Many2many(
        'res.partner', string='Khách hàng cần đồng bộ',
        help="Chỉ dùng khi chọn chế độ Theo khách hàng",
    )
    serial_number = fields.Char(
        string='Số Serial',
        help="Nhập số serial để đồng bộ (chỉ dùng khi chọn chế độ Theo số serial)",
    )
    batch_size = fields.Integer(
        string='Số serial mỗi batch',
        default=50,
        help="Mỗi lượt chạy nền xử lý từ 1 đến 500 serial hiện có.",
    )
    last_batch_status = fields.Char(
        string='Batch gần nhất',
        compute='_compute_last_batch_status',
    )

    @api.depends('sync_type')
    def _compute_last_batch_status(self):
        state_labels = {
            'queued': _('Đang chờ'),
            'running': _('Đang chạy'),
            'done': _('Hoàn tất'),
            'done_with_errors': _('Hoàn tất có lỗi'),
            'failed': _('Thất bại'),
        }
        for wizard in self:
            if wizard.sync_type != 'existing':
                wizard.last_batch_status = False
                continue
            job = self.env['stock.lot.sync.batch'].sudo().search([
                ('company_id', '=', self.env.company.id),
            ], order='id desc', limit=1)
            if not job:
                wizard.last_batch_status = _('Chưa có batch nào.')
                continue
            wizard.last_batch_status = _(
                '%(state)s - đã xử lý %(processed)s/%(total)s, '
                'thành công %(success)s, lỗi %(failure)s.'
            ) % {
                'state': state_labels.get(job.state, job.state),
                'processed': job.processed_count,
                'total': job.total_count,
                'success': job.success_count,
                'failure': job.failure_count,
            }

    def action_sync_serial_item(self):
        self.ensure_one()
        if self.sync_type == 'existing':
            return self._queue_existing_serial_sync()
        return self._sync_serial_items()

    def _queue_existing_serial_sync(self):
        self.ensure_one()
        if not 1 <= self.batch_size <= 500:
            raise UserError(_("Số serial mỗi batch phải từ 1 đến 500."))

        cron = self.env.ref(
            'dat_sync_sap.ir_cron_sync_existing_stock_lots'
        ).sudo()
        if not cron.active:
            raise UserError(_(
                "Scheduled action đồng bộ serial theo batch đang bị tắt. "
                "Vui lòng bật scheduled action trước khi chạy."
            ))

        job = self.env['stock.lot.sync.batch'].queue_existing_lots(
            company=self.env.company,
            batch_size=self.batch_size,
            requested_by=self.env.user,
        )
        cron._trigger()

        action = self._show_notification(
            'success',
            _(
                'Đã đưa %(total)s serial hiện có vào hàng đợi. '
                'Hệ thống sẽ chạy nền theo từng batch %(batch)s serial.'
            ) % {
                'total': job.total_count,
                'batch': job.batch_size,
            },
        )
        action['params'].update({
            'sticky': True,
            'next': {'type': 'ir.actions.act_window_close'},
        })
        return action

    def _sync_serial_items(self):
        error_groups = {}

        if self.sync_type == 'partner':
            partners = self._validate_and_collect_partners(error_groups)
            for card_code, card_name in partners:
                try:
                    with self.env.cr.savepoint():
                        items = self._fetch_serial_items(
                            card_code=card_code,
                            card_name=card_name,
                            error_groups=error_groups,
                        )
                        for item in items or []:
                            self._process_serial_item(item, card_name, error_groups)
                except Exception as error:
                    _logger.exception(
                        "Đồng bộ SerialItem thất bại | card_code=%s | card_name=%s",
                        card_code,
                        card_name,
                    )
                    self._add_error(
                        "Lỗi đồng bộ SerialItem",
                        f"{card_name} – {error}",
                        error_groups,
                    )

        else:  # sync_type == 'serial'
            serial_number = (self.serial_number or '').strip()
            if not serial_number:
                raise UserError("Vui lòng nhập số serial để đồng bộ.")
            self.serial_number = serial_number
            try:
                with self.env.cr.savepoint():
                    self._sync_single_serial(
                        serial_number,
                        error_groups=error_groups,
                    )
            except Exception as error:
                _logger.exception(
                    "Đồng bộ SerialItem thất bại | serial=%s",
                    serial_number,
                )
                self._add_error(
                    "Lỗi đồng bộ SerialItem",
                    f"{serial_number} – {error}",
                    error_groups,
                )
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
        serial_number = (serial_number or '').strip()
        payload = {
            'CardCode': '' if serial_number else card_code,
            'SerialNumber': serial_number,
        }
        response = self.api_method(
            self.api_url + '/SerialItem',
            headers=self.api_headers,
            json=payload,
            timeout=30,
        )
        if not response.ok:
            raise UserError(
                _(
                    'API SerialItem trả về HTTP %(status)s cho %(lookup)s: '
                    '%(message)s'
                ) % {
                    'status': response.status_code,
                    'lookup': serial_number or card_name or card_code,
                    'message': (response.text or response.reason or '')[:500],
                }
            )

        try:
            response_json = response.json()
        except ValueError as error:
            raise UserError(
                _('API SerialItem trả về dữ liệu không phải JSON cho %s.')
                % (serial_number or card_name or card_code)
            ) from error

        if (
            isinstance(response_json, dict)
            and str(response_json.get('status', '')).upper() == 'FALSE'
        ):
            raise UserError(
                _('API SerialItem báo lỗi: %s') % (
                    response_json.get('msg')
                    or response_json.get('message')
                    or response_json
                )
            )

        items = self._extract_serial_items(response_json)
        if serial_number:
            normalized_serial = serial_number.casefold()
            items = [
                item
                for item in items
                if isinstance(item, dict)
                and str(item.get('SerialNumber') or '').strip().casefold()
                == normalized_serial
            ][-1:]

        if not items:
            self._add_error(
                (
                    "Không có dữ liệu API trả về cho Serial Number"
                    if serial_number
                    else "Không có dữ liệu API trả về cho các khách hàng"
                ),
                serial_number or card_name,
                error_groups,
            )
        return items

    def _sync_single_serial(self, serial_number, lot=False, error_groups=None):
        self.ensure_one()
        serial_number = (serial_number or '').strip()
        if not serial_number:
            raise UserError(_('Số serial không được để trống.'))

        if error_groups is None:
            error_groups = {}
        items = self._fetch_serial_items(
            card_code='',
            card_name='',
            error_groups=error_groups,
            serial_number=serial_number,
        )
        for item in items or []:
            self._process_serial_item(
                item,
                serial_number,
                error_groups,
                serial_number=serial_number,
                lot=lot,
            )
        return error_groups

    def _extract_serial_items(self, response_json):
        if isinstance(response_json, list):
            return response_json
        if not isinstance(response_json, dict):
            return []
        result = response_json.get('result') or response_json.get('data') or {}
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            if isinstance(result.get('Items'), list):
                return result.get('Items')
            if result.get('SerialNumber'):
                return [result]
        return []

    def _process_serial_item(
        self, item, card_name, error_groups, serial_number=None, lot=False,
    ):
        if not serial_number:
            serial_number = item.get('SerialNumber')
        if card_name and not self._check_and_log(serial_number, error_groups,
                                                 "Không có serial number cho các khách hàng", card_name):
            return
        if not lot:
            lot = self.env['stock.lot'].search([
                ('name', '=', serial_number),
            ], limit=1)

        product = self.env['stock.lot']._find_product_by_item_code(item.get('ItemCode'))
        if not product and lot:
            product = lot.product_id
        if not product:
            product = self.env['stock.lot']._get_or_create_product_for_serial(item, serial_number)
        if not self._check_and_log(product, error_groups,
                                   "Không có product tương ứng với serial number", serial_number):
            return
        buyer_code = str(item.get('BuyerCode') or '').strip()
        owner_code = str(item.get('OwnerCode') or '').strip()
        buyer = self._find_serial_partner(
            buyer_code,
            "Không có khách hàng với mã serial number",
            serial_number,
            error_groups,
            partner_name=item.get('BuyerName'),
        ) if buyer_code else False
        owner = self._find_serial_partner(
            owner_code,
            "Không có người sở hữu với mã serial number",
            serial_number,
            error_groups,
            partner_name=item.get('OwnerName'),
        ) if owner_code else buyer
        if not buyer and not buyer_code and owner:
            buyer = owner

        if not product or not buyer or not owner:
            if not buyer_code and not owner_code:
                self._add_error(
                    "SerialNumber không có BuyerCode/OwnerCode",
                    serial_number,
                    error_groups,
                )
            return

        employee = self.env['hr.employee'].search([('sap_slp_code', '=', item.get('SlpCode'))], limit=1) if item.get(
            'SlpCode') not in (None, '', 'null', False) else False
        self._upsert_stock_lot(item, product, buyer, owner, employee, lot)

    def _find_serial_partner(
        self, card_code, error_key, error_value, error_groups,
        partner_name=False,
    ):
        partners = self.env['res.partner'].search([
            ('card_code', '=', card_code),
        ])
        if not self._check_and_log(
            partners, error_groups, error_key, error_value,
        ):
            return self.env['res.partner']

        normalized_name = str(partner_name or '').strip().casefold()
        if normalized_name:
            named_partner = partners.filtered(
                lambda partner: normalized_name in {
                    (partner.name or '').strip().casefold(),
                    (partner.display_name or '').strip().casefold(),
                    (partner.company_name or '').strip().casefold(),
                }
            )[:1]
            if named_partner:
                return named_partner
        return partners[:1]

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
            'buyer_id': buyer.id,
            'owner_id': owner.id,
        }
        if item.get('DeliveryDate'):
            vals['warranty_start_date'] = self._parse_date(item['DeliveryDate'])
        if item.get('WarrantyMonth') not in (None, '', False, 'null'):
            vals['warranty_month'] = self._parse_integer(
                item['WarrantyMonth'], 'WarrantyMonth', item.get('SerialNumber'),
            )
        if item.get('VendorWarrantyExpiry'):
            vals['vendor_warranty_expiry'] = self._parse_date(
                item['VendorWarrantyExpiry']
            )
        if employee:
            vals['saleperson_id'] = employee.id

        if lot:
            # A serial with stock moves cannot safely change products. Keep its
            # product and refresh only mutable SAP master data.
            if not lot.product_id:
                vals['product_id'] = product.id
            lot._write_sap_serial_values(
                vals,
                owner_is_fallback=not str(item.get('OwnerCode') or '').strip(),
            )
            return lot
        vals.update({
            'name': item.get('SerialNumber'),
            'product_id': product.id,
            'note': f"Import từ API ngày {fields.Date.today()}",
        })
        return self.env['stock.lot'].create(vals)

    @staticmethod
    def _parse_integer(value, field_name, serial_number):
        try:
            return int(float(value))
        except (OverflowError, TypeError, ValueError) as error:
            raise UserError(
                _(
                    'Giá trị %(field)s không hợp lệ cho serial '
                    '%(serial)s: %(value)s'
                ) % {
                    'field': field_name,
                    'serial': serial_number or '',
                    'value': value,
                }
            ) from error

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
