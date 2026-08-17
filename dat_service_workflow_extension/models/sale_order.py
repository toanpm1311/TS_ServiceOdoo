import base64
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.modules.module import get_module_resource


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    _REPORT_FILENAME_SAFE_PATTERN = r'[\\/:*?"<>|]+'

    _PRINT_MOJIBAKE_MARKERS = ('Ã', 'Â', 'Ä', 'Æ', 'áº', 'á»', 'â€', 'ï»¿')

    SERVICE_QUOTATION_STATUS_SELECTION = [
        ('waiting_quotation', 'Ch\u1edd b\u00e1o gi\u00e1'),
        ('waiting_customer_approval', 'Ch\u1edd kh\u00e1ch h\u00e0ng \u0111\u1ed3ng \u00fd'),
        ('customer_approved_repair', 'KH \u0111\u1ed3ng \u00fd s\u1eeda ch\u1eefa'),
        ('customer_refused_repair', 'KH kh\u00f4ng \u0111\u1ed3ng \u00fd s\u1eeda ch\u1eefa'),
        ('customer_refused_repair_delivering', 'KH kh\u00f4ng \u0111\u1ed3ng \u00fd s\u1eeda ch\u1eefa, \u0111ang giao'),
        ('customer_refused_repair_delivered', 'KH kh\u00f4ng \u0111\u1ed3ng \u00fd s\u1eeda ch\u1eefa, \u0111\u00e3 giao tr\u1ea3'),
        ('waiting_parts_issue', 'Ch\u1edd xu\u1ea5t linh ki\u1ec7n'),
        ('parts_issued', '\u0110\u00e3 xu\u1ea5t linh ki\u1ec7n'),
        ('waiting_new_unit_warranty', 'Ch\u1edd b\u1ea3o h\u00e0nh b\u1ed9 m\u1edbi'),
        ('new_unit_warranted_delivering', '\u0110\u00e3 b\u1ea3o h\u00e0nh b\u1ed9 m\u1edbi, \u0111ang giao'),
        ('new_unit_warranted_delivered', '\u0110\u00e3 b\u1ea3o h\u00e0nh b\u1ed9 m\u1edbi, \u0111\u00e3 giao'),
        ('done', 'Ho\u00e0n th\u00e0nh'),
        ('done_delivering', 'Ho\u00e0n th\u00e0nh, \u0111ang giao'),
        ('done_delivered', 'Ho\u00e0n th\u00e0nh, \u0111\u00e3 giao'),
        ('not_repaired', 'Kh\u00f4ng s\u1eeda ch\u1eefa'),
        ('not_repaired_delivering', 'Kh\u00f4ng s\u1eeda ch\u1eefa, \u0111ang giao'),
        ('not_repaired_delivered', 'Kh\u00f4ng s\u1eeda ch\u1eefa, \u0111\u00e3 giao'),
        ('stock_received', '\u0110\u00e3 nh\u1eadp kho'),
    ]

    main_product_id = fields.Many2one('product.product', string='S\u1ea3n ph\u1ea9m ch\u00ednh')
    main_product_code = fields.Char(string='M\u00e3 s\u1ea3n ph\u1ea9m ch\u00ednh')
    service_quotation_status = fields.Selection(
        SERVICE_QUOTATION_STATUS_SELECTION,
        string='Tr\u1ea1ng th\u00e1i b\u00e1o gi\u00e1',
        default='waiting_quotation',
        copy=False,
        index=True,
        tracking=True,
    )
    delivery_employee_note = fields.Char(
        string='Nh\u00e2n vi\u00ean giao h\u00e0ng (ghi tay)',
        copy=False,
    )
    delivery_time_confirmed = fields.Boolean(
        string='X\u00e1c \u0111\u1ecbnh th\u1eddi gian giao',
        copy=False,
    )
    delivery_confirmed_datetime = fields.Datetime(
        string='Th\u1eddi gian giao',
        copy=False,
    )

    @api.onchange('delivery_time_confirmed')
    def _onchange_delivery_time_confirmed(self):
        for order in self:
            if order.delivery_time_confirmed and not order.delivery_confirmed_datetime:
                order.delivery_confirmed_datetime = fields.Datetime.now()
            elif not order.delivery_time_confirmed:
                order.delivery_confirmed_datetime = False

    def _get_dat_report_logo_data_uri(self, company=False):
        companies = (
            company,
            self.env.ref('base.main_company', raise_if_not_found=False),
            self.env.company,
        )
        for candidate in companies:
            if candidate and candidate.sudo().logo:
                logo = candidate.sudo().logo
                if isinstance(logo, bytes):
                    logo = logo.decode()
                return 'data:image/png;base64,%s' % logo

        logo_path = get_module_resource(
            'dat_website_helpdesk', 'static', 'src', 'img', 'dat-color.png'
        )
        if not logo_path:
            return ''
        with open(logo_path, 'rb') as logo_file:
            logo_data = base64.b64encode(logo_file.read()).decode()
        return 'data:image/png;base64,%s' % logo_data

    def _get_dat_report_header_data_uri(self):
        header_path = get_module_resource(
            'dat_website_helpdesk', 'static', 'src', 'img', 'header.png'
        )
        if not header_path:
            return ''
        with open(header_path, 'rb') as header_file:
            header_data = base64.b64encode(header_file.read()).decode()
        return 'data:image/png;base64,%s' % header_data

    def _clean_print_text(self, value):
        if value in (False, None):
            return ''
        text = str(value)
        for _iteration in range(2):
            current_score = sum(text.count(marker) for marker in self._PRINT_MOJIBAKE_MARKERS)
            if not current_score:
                break
            fixed = self._repair_print_mojibake_once(text)
            fixed_score = sum(fixed.count(marker) for marker in self._PRINT_MOJIBAKE_MARKERS)
            if fixed == text or fixed_score >= current_score:
                break
            text = fixed
        return text

    @staticmethod
    def _legacy_print_byte(character):
        try:
            return character.encode('cp1252')
        except UnicodeError:
            if ord(character) <= 255:
                return bytes((ord(character),))
            return False

    def _repair_print_mojibake_once(self, text):
        repaired = []
        index = 0
        while index < len(text):
            for length in (4, 3, 2):
                chunk = text[index:index + length]
                if len(chunk) != length:
                    continue
                legacy_bytes = [self._legacy_print_byte(character) for character in chunk]
                if not all(legacy_bytes):
                    continue
                try:
                    decoded = b''.join(legacy_bytes).decode('utf-8')
                except UnicodeError:
                    continue
                if len(decoded) == 1 and ord(decoded) > 127:
                    repaired.append(decoded)
                    index += length
                    break
            else:
                repaired.append(text[index])
                index += 1
        return ''.join(repaired)

    @api.depends('ticket_id')
    def _compute_warehouse_domain(self):
        super()._compute_warehouse_domain()
        extra_codes = self._get_extra_service_warehouse_codes()
        if not extra_codes:
            return
        extra_warehouses = self.env['stock.warehouse'].search([('code', 'in', extra_codes)])
        for order in self:
            if not order.ticket_id or not extra_warehouses:
                continue
            allowed = order.warehouse_domain_ids | extra_warehouses.filtered(
                lambda wh: not wh.company_id or wh.company_id == order.ticket_id.branch
            )
            order.warehouse_domain_ids = [(6, 0, allowed.ids)]

    def _get_extra_service_warehouse_codes(self):
        raw_codes = self.env['ir.config_parameter'].sudo().get_param(
            'dat_service_workflow_extension.extra_service_warehouse_codes',
            'HCMVP239',
        )
        return [code.strip() for code in raw_codes.split(',') if code.strip()]

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        product_ids = self.env.context.get('default_product_ids') or []
        ticket = self.env['ticket.helpdesk'].browse(
            self.env.context.get('default_ticket_id')
        ).exists()
        add_fixing_line = bool(
            ticket
            and ticket.product_warranty_status in ('out_of_warranty', 'not_eligible_for_warranty')
            and ticket.require_materials == 'yes'
        )
        if self.env.context.get('default_main_product_id'):
            values.setdefault('main_product_id', self.env.context['default_main_product_id'])
        if self.env.context.get('default_main_product_code'):
            values.setdefault('main_product_code', self.env.context['default_main_product_code'])

        document_note = self.env.context.get('default_document_note') or self.env.context.get('default_note')
        if document_note:
            values.setdefault('document_note', document_note)
            values.setdefault('note', document_note)

        if product_ids and not values.get('order_line'):
            products = self.env['product.product'].browse(product_ids).exists()
            main_product = self.env['product.product'].browse(
                self.env.context.get('default_main_product_id')
            ).exists()
            lines = []
            for product in products:
                lines.append((0, 0, self._prepare_default_material_line(product)))
                if add_fixing_line and main_product and product == main_product:
                    fixing_product = self._get_fixing_product_for_main_product(product)
                    if fixing_product:
                        lines.append((0, 0, self._prepare_default_material_line(fixing_product, create_sap=False)))
            values['order_line'] = lines
        return values

    def _get_fixing_product_for_main_product(self, product):
        code = (product.default_code or '').strip()
        if not code:
            return self.env['product.product']

        candidates = self.env['product.product'].search([
            ('id', '!=', product.id),
            ('default_code', '=', code),
            ('name', 'ilike', 'FIXING'),
        ])
        if not candidates:
            return candidates

        service_candidates = candidates.filtered(
            lambda candidate: (
                getattr(candidate, 'detailed_type', False)
                or getattr(candidate.product_tmpl_id, 'detailed_type', False)
                or getattr(candidate, 'type', False)
            ) == 'service'
        )
        return (service_candidates or candidates)[:1]

    def _prepare_default_material_line(self, product, create_sap=True):
        return {
            'product_id': product.id,
            'name': product.display_name,
            'product_uom_qty': 1.0,
            'product_uom': product.uom_so_id.id or product.uom_id.id,
            'sap_wmonth': 0,
            'manufacturer_warranty_month': 0,
            'onhand_quantity': product.qty_available,
            'create_sap': create_sap,
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            ticket_id = vals.get('ticket_id') or self.env.context.get('default_ticket_id')
            if ticket_id:
                ticket = self.env['ticket.helpdesk'].browse(ticket_id)
                product = ticket._get_main_quotation_product() if ticket.exists() else False
                if product:
                    vals.setdefault('main_product_id', product.id)
                    vals.setdefault('main_product_code', product.default_code or '')
                document_note = ticket._build_document_note() if ticket.exists() else False
                if document_note:
                    vals.setdefault('document_note', document_note)
                    vals.setdefault('note', document_note)
        return super().create(vals_list)

    def action_print_standard_quotation(self):
        return self._action_open_standard_quotation_export_wizard()

    def _action_open_standard_quotation_export_wizard(self):
        orders = self.exists()
        if not orders:
            raise UserError(_('Vui lòng chọn ít nhất một báo giá để xuất file.'))
        orders._validate_standard_quotation_export()
        return {
            'name': _('Xuất phiếu báo giá'),
            'type': 'ir.actions.act_window',
            'res_model': 'standard.quotation.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_ids': [fields.Command.set(orders.ids)],
                'default_export_mode': 'summary',
            },
        }

    def _validate_standard_quotation_export(self):
        if not self:
            raise UserError(_('Vui lòng chọn ít nhất một báo giá để xuất file.'))

        quotation_partners = self.env['res.partner']
        for order in self:
            quotation_partners |= order.ticket_id.owner_id or order.partner_id
        if len(quotation_partners) > 1:
            raise UserError(_('Chỉ được xuất chung các báo giá cùng khách hàng.'))
        return True

    def _get_standard_quotation_line_ticket(self, line):
        self.ensure_one()
        if 'ts_source_ticket_id' in line._fields and line.ts_source_ticket_id:
            return line.ts_source_ticket_id
        return self.ticket_id

    def _get_standard_quotation_ticket_product(self, ticket):
        self.ensure_one()
        if ticket and hasattr(ticket, '_get_main_quotation_product'):
            return ticket._get_main_quotation_product()
        if ticket:
            return ticket.product_id
        return self.main_product_id

    def _prepare_standard_quotation_detailed_line(self, line):
        self.ensure_one()
        ticket = self._get_standard_quotation_line_ticket(line)
        main_product = self._get_standard_quotation_ticket_product(ticket)
        return {
            'model': main_product.default_code or main_product.display_name or '',
            'serial': ticket.stock_lot_id.name if ticket else '',
            'code': line.product_id.default_code or self.main_product_code or '',
            'description': line.name or line.product_id.display_name or '',
            'quantity': line.product_uom_qty,
            'price_unit': line.price_unit,
            'price_subtotal': line.price_subtotal,
            'warranty': line.quotation_warranty_term or '',
        }

    @staticmethod
    def _is_standard_quotation_service_line(line):
        product_code = (line.product_id.default_code or '').strip().upper()
        product_name = (line.product_id.display_name or '').strip().lower()
        return product_code == 'PHIDICHVU' or 'phí dịch vụ' in product_name

    def _prepare_standard_quotation_summary_lines(self, ticket, lines):
        self.ensure_one()
        main_product = self._get_standard_quotation_ticket_product(ticket)
        model = main_product.default_code or main_product.display_name or ''
        serial = ticket.stock_lot_id.name if ticket else ''
        main_lines = lines.filtered(lambda line: line.product_id == main_product)
        service_lines = lines.filtered(self._is_standard_quotation_service_line)
        component_lines = lines - main_lines - service_lines
        main_line = main_lines[:1]
        service_line = service_lines[:1]
        repair_amount = sum(component_lines.mapped('price_subtotal'))
        if not component_lines:
            repair_amount = sum((lines - main_lines).mapped('price_subtotal'))

        component_warranties = []
        seen_warranties = set()
        for line in component_lines.filtered('quotation_warranty_term'):
            component_label = (
                line.product_id.default_code
                or line.product_id.display_name
                or line.name
                or _('Linh kiện')
            )
            warranty_text = _('%(component)s: %(term)s') % {
                'component': component_label,
                'term': line.quotation_warranty_term,
            }
            if warranty_text not in seen_warranties:
                component_warranties.append(warranty_text)
                seen_warranties.add(warranty_text)

        main_description = (
            main_line.name
            or main_product.display_name
            or model
            or _('Sản phẩm chính')
        )
        service_description = (
            service_line.name
            or service_line.product_id.display_name
            or _('Phí dịch vụ sửa chữa')
        )
        service_code = service_line.product_id.default_code or 'PHIDICHVU'

        return [
            {
                'model': model,
                'serial': serial,
                'code': main_product.default_code or model,
                'description': main_description,
                'quantity': 1.0,
                'price_unit': 0.0,
                'price_subtotal': 0.0,
                'warranty': main_line.quotation_warranty_term or '',
            },
            {
                'model': model,
                'serial': serial,
                'code': service_code,
                'description': service_description,
                'quantity': 1.0,
                'price_unit': repair_amount,
                'price_subtotal': repair_amount,
                'warranty': '; '.join(component_warranties)
                or service_line.quotation_warranty_term
                or '',
            },
        ]

    def _get_standard_quotation_display_lines(self, export_mode='summary'):
        self.ensure_one()
        report_lines = self.order_line.filtered(
            lambda line: not line.display_type and line.product_id
        ).sorted(key=lambda line: (line.sequence, line.id))
        if export_mode == 'detailed':
            return [
                self._prepare_standard_quotation_detailed_line(line)
                for line in report_lines
            ]

        grouped_lines = {}
        ticket_order = []
        for line in report_lines:
            ticket = self._get_standard_quotation_line_ticket(line)
            ticket_key = ticket.id if ticket else 0
            if ticket_key not in grouped_lines:
                grouped_lines[ticket_key] = self.env['sale.order.line']
                ticket_order.append((ticket_key, ticket))
            grouped_lines[ticket_key] |= line

        summary_lines = []
        for ticket_key, ticket in ticket_order:
            summary_lines.extend(
                self._prepare_standard_quotation_summary_lines(
                    ticket, grouped_lines[ticket_key]
                )
            )
        return summary_lines

    def _get_standard_quotation_report_filename(self):
        self.ensure_one()
        ticket = self.ticket_id
        lot = ticket.stock_lot_id if ticket else self.env['stock.lot']
        model = (
            self.main_product_code
            or self.main_product_id.default_code
            or (ticket.product_id.default_code if ticket else '')
            or ''
        )
        serial = lot.name or ''
        owner_name = (
            ticket._service_owner_company_name()
            if ticket and hasattr(ticket, '_service_owner_company_name')
            else ''
        ) or self.partner_id.display_name or self.name or ''

        if model and serial:
            name = '%s-%s' % (model, serial)
        elif model:
            name = model
        elif serial:
            name = serial
        else:
            name = owner_name

        name = re.sub(self._REPORT_FILENAME_SAFE_PATTERN, '-', name).strip(' .-')
        return 'Bao gia - %s' % (name or self.name or '')

    def action_print_standard_quotation_batch(self):
        return self._action_open_standard_quotation_export_wizard()

    def action_reopen_service_quotation_for_edit(self):
        for order in self:
            if (order.sap_status or '').strip():
                raise UserError(_('B\u00e1o gi\u00e1 %s \u0111\u00e3 c\u00f3 s\u1ed1 ch\u1ee9ng t\u1eeb SAP v\u00e0 kh\u00f4ng th\u1ec3 m\u1edf l\u1ea1i.') % order.name)
            order.status = 'draft'
        return True

    def action_create_sap_so_single(self):
        return super().action_create_sap_so_single()

    def action_create_sap_dxvt_single(self):
        for order in self:
            if order.wf_external_id != 'workflow_1':
                raise UserError(_('Chỉ hỗ trợ tạo ĐXVT cho báo giá TechService workflow 1.'))
            if not hasattr(order, 'create_sap_doc'):
                raise UserError(_('Không tìm thấy hàm tạo chứng từ SAP trên báo giá %s.') % (order.name or order.display_name))

            doc_number = order.create_sap_doc(doc_type='DXVT')
            if not doc_number:
                raise UserError(_('SAP không trả về số ĐXVT cho báo giá %s.') % (order.name or order.display_name))

            if order.ticket_id and 'sap_dxvt_order_number' in order.ticket_id._fields:
                order.ticket_id.sap_dxvt_order_number = doc_number
            message = _('Tạo ĐXVT SAP thành công: %s') % doc_number
            order.message_post(body=message)
            if order.ticket_id:
                order.ticket_id.message_post(body=message)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'sticky': False,
                'message': _('Đã tạo ĐXVT SAP thành công.'),
            },
        }

    def action_send_standard_quotation_to_sales(self):
        template = self.env.ref(
            'dat_service_workflow_extension.email_template_standard_quotation_to_sales',
            raise_if_not_found=False,
        )
        if not template:
            raise UserError(_('Kh\u00f4ng t\u00ecm th\u1ea5y m\u1eabu email g\u1eedi phi\u1ebfu b\u00e1o gi\u00e1.'))

        for order in self:
            salesperson = order.ticket_id.saleperson_id if order.ticket_id else False
            email_to = (
                (salesperson.work_email if salesperson else False)
                or (salesperson.user_id.email if salesperson and salesperson.user_id else False)
                or (salesperson.user_id.login if salesperson and salesperson.user_id else False)
                or order.user_id.email
            )
            if not email_to:
                raise UserError(_('Kh\u00f4ng th\u1ec3 g\u1eedi b\u00e1o gi\u00e1 %s v\u00ec nh\u00e2n vi\u00ean kinh doanh ch\u01b0a c\u00f3 email.') % order.name)
            template.sudo().send_mail(
                order.id,
                force_send=True,
                email_values={'email_to': email_to},
            )
            order.message_post(body=_('Phi\u1ebfu b\u00e1o gi\u00e1 \u0111\u00e3 \u0111\u01b0\u1ee3c g\u1eedi cho nh\u00e2n vi\u00ean kinh doanh: %s') % email_to)
        return True
