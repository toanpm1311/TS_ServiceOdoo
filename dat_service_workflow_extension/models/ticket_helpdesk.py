import base64
import io
import os

import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.modules.module import get_module_resource


class TicketHelpDesk(models.Model):
    _inherit = 'ticket.helpdesk'

    checklist_ids = fields.One2many('service.work.checklist', 'ticket_id', string='Phi\u1ebfu ki\u1ec3m tra c\u00f4ng vi\u1ec7c')
    checklist_count = fields.Integer(string='S\u1ed1 phi\u1ebfu ki\u1ec3m tra', compute='_compute_checklist_count')
    has_pending_sap_so = fields.Boolean(
        string='Co SO SAP can tao',
        compute='_compute_has_pending_sap_so',
    )
    allow_next_remote_warranty_ticket = fields.Boolean(
        string='Cho phep tao lai BH tu xa',
        copy=False,
        tracking=True,
    )
    manufacturer_warranty_month = fields.Integer(
        string='B\u1ea3o h\u00e0nh h\u00e3ng (th\u00e1ng)',
        related='product_id.sap_wmonth_dist',
        readonly=True,
    )
    manufacturer_warranty_end_date = fields.Datetime(
        string='Ng\u00e0y h\u1ebft h\u1ea1n b\u1ea3o h\u00e0nh h\u00e3ng',
        related='stock_lot_id.manufacturer_warranty_end_date',
        readonly=True,
    )

    @api.depends('checklist_ids')
    def _compute_checklist_count(self):
        for ticket in self:
            ticket.checklist_count = len(ticket.checklist_ids)

    @api.depends('sale_order_ids.sap_status', 'sale_order_ids.sap_is_create_so')
    def _compute_has_pending_sap_so(self):
        for ticket in self:
            ticket.has_pending_sap_so = bool(ticket.sale_order_ids.filtered(
                lambda so: not (so.sap_status or '').strip()
                and (
                    so.sap_is_create_so
                    if 'sap_is_create_so' in so._fields
                    else True
                )
            ))

    def action_allow_next_remote_warranty_ticket(self):
        for ticket in self:
            ticket.allow_next_remote_warranty_ticket = True
            ticket.message_post(body=_('Da cho phep tao lai bao hanh tu xa cho serial nay mot lan.'))
        return True

    def _get_main_quotation_product(self):
        self.ensure_one()
        lot = getattr(self, 'new_stock_lot_id', False) or self.stock_lot_id
        return lot.product_id or self.product_id

    def _get_board_products_from_main_product(self, product):
        self.ensure_one()
        board_codes = [
            code.strip()
            for code in re.split(r'[,;\n\r]+', product.sap_serial_num or '')
            if code.strip()
        ]
        if not board_codes:
            return self.env['product.product']
        return self.env['product.product'].search([
            ('default_code', 'in', board_codes),
        ])

    def _clean_print_text(self, value):
        if value in (False, None):
            return ''
        text = str(value)
        if any(marker in text for marker in ('Ã', 'Â')):
            try:
                return text.encode('cp1252').decode('utf-8')
            except UnicodeError:
                return text
        if 'Ã' not in text and 'Â' not in text:
            return text
        try:
            return text.encode('cp1252').decode('utf-8')
        except UnicodeError:
            return text

    def _service_owner_company_name(self):
        self.ensure_one()
        owner = self.owner_id
        if not owner:
            return self.customer_company_name or (self.customer_id.display_name if self.customer_id else '')
        company = owner.commercial_partner_id if owner.commercial_partner_id != owner else owner.parent_id
        return (
            owner.company_name
            or (company.display_name if company else '')
            or (self.customer_id.display_name if self.customer_id else '')
            or owner.display_name
        )

    def _service_contact_name(self):
        self.ensure_one()
        return self.customer_contact_name or (self.owner_id.display_name if self.owner_id else '')

    def _service_contact_phone(self):
        self.ensure_one()
        return self.customer_phone or self.customer_id.phone or self.customer_id.mobile or ''

    def _fallback_owner_phone_from_contact(self):
        for ticket in self:
            if ticket.owner_id and not ticket.owner_phone and ticket.customer_phone:
                ticket.with_context(skip_owner_phone_contact_fallback=True).owner_phone = ticket.customer_phone

    def _service_salesperson_from_owner(self):
        self.ensure_one()
        return (
            self.owner_id.sudo().sale_person
            or self.customer_id.sudo().sale_person
            or False
        )

    def _sync_salesperson_from_owner(self):
        for ticket in self:
            salesperson = ticket._service_salesperson_from_owner()
            if salesperson and ticket.saleperson_id != salesperson:
                ticket.with_context(skip_service_salesperson_sync=True).saleperson_id = salesperson

    @api.onchange('customer_phone', 'owner_id')
    def _onchange_owner_phone_contact_fallback(self):
        for ticket in self:
            if ticket.owner_id and not ticket.owner_phone and ticket.customer_phone:
                ticket.owner_phone = ticket.customer_phone
            salesperson = ticket._service_salesperson_from_owner()
            if salesperson:
                ticket.saleperson_id = salesperson

    @api.onchange('stock_lot_id')
    def _onchange_stock_lot_id_service_extension(self):
        for ticket in self:
            lot = ticket.stock_lot_id
            if not lot:
                continue
            if lot.buyer_id:
                ticket.customer_id = lot.buyer_id
                ticket.customer_phone = lot.buyer_phone or lot.buyer_id.phone or lot.buyer_id.mobile
                ticket.customer_company_name = lot.buyer_id.company_name or lot.buyer_id.display_name
            if lot.owner_id:
                ticket.owner_id = lot.owner_id
                ticket.owner_phone = lot.owner_phone or lot.owner_id.mobile
                ticket.owner_email = lot.owner_id.email
                ticket.owner_address = lot.owner_id.contact_address
                if not ticket.owner_phone and ticket.customer_phone:
                    ticket.owner_phone = ticket.customer_phone
                if not lot.buyer_id:
                    ticket.customer_company_name = ticket._service_owner_company_name()

    def _sync_customer_from_lot_service_extension(self, vals):
        lot_id = vals.get('stock_lot_id')
        if not lot_id:
            return
        lot = self.env['stock.lot'].browse(lot_id)
        if not lot.exists():
            return
        if lot.buyer_id and not vals.get('customer_id'):
            vals['customer_id'] = lot.buyer_id.id
        if lot.buyer_id and not vals.get('customer_phone'):
            vals['customer_phone'] = lot.buyer_phone or lot.buyer_id.phone or lot.buyer_id.mobile
        if lot.buyer_id and not vals.get('customer_company_name'):
            vals['customer_company_name'] = lot.buyer_id.company_name or lot.buyer_id.display_name
        if lot.owner_id and not vals.get('owner_id'):
            vals.update({
                'owner_id': lot.owner_id.id,
                'owner_phone': lot.owner_phone or lot.owner_id.mobile,
                'owner_email': lot.owner_id.email,
                'owner_address': lot.owner_id.contact_address,
            })
        if vals.get('owner_id') and not vals.get('owner_phone') and vals.get('customer_phone'):
            vals['owner_phone'] = vals['customer_phone']
        if lot.owner_id and not lot.buyer_id and not vals.get('customer_company_name'):
            owner = lot.owner_id
            company = owner.commercial_partner_id if owner.commercial_partner_id != owner else owner.parent_id
            vals['customer_company_name'] = (
                owner.company_name
                or (company.display_name if company else '')
                or (lot.buyer_id.display_name if lot.buyer_id else '')
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sync_customer_from_lot_service_extension(vals)
        tickets = super().create(vals_list)
        tickets._fallback_owner_phone_from_contact()
        tickets._sync_salesperson_from_owner()
        return tickets

    def write(self, vals):
        vals = dict(vals)
        self._sync_customer_from_lot_service_extension(vals)
        result = super().write(vals)
        if not self.env.context.get('skip_owner_phone_contact_fallback'):
            self._fallback_owner_phone_from_contact()
        if (
            not self.env.context.get('skip_service_salesperson_sync')
            and {'owner_id', 'customer_id'} & set(vals)
        ):
            self._sync_salesperson_from_owner()
        return result

    def action_create_quotation(self):
        action = super().action_create_quotation()
        if not isinstance(action, dict):
            return action

        ctx = dict(action.get('context') or {})
        product = self._get_main_quotation_product()
        if product:
            product_ids = list(ctx.get('default_product_ids') or [])
            if product.id not in product_ids:
                product_ids.insert(0, product.id)
            for board_product in self._get_board_products_from_main_product(product):
                if board_product.id not in product_ids:
                    product_ids.append(board_product.id)
            ctx.update({
                'default_product_ids': product_ids,
                'default_main_product_id': product.id,
                'default_main_product_code': product.default_code or '',
            })

        document_note = self._build_document_note()
        ctx.setdefault('default_document_note', document_note)
        ctx.setdefault('default_note', document_note)
        action['context'] = ctx
        return action

    def action_print_work_checklist(self):
        self.ensure_one()
        if self.implementation_work_ids:
            self.implementation_work_ids._sync_service_work_checklists()
        return self.env.ref(
            'dat_service_workflow_extension.action_report_service_work_checklist'
        ).report_action(self)

    def action_export_work_checklist_xlsx(self):
        self.ensure_one()
        if self.implementation_work_ids:
            self.implementation_work_ids._sync_service_work_checklists()

        try:
            import xlsxwriter
        except ImportError as error:
            raise UserError(_('Missing Python library xlsxwriter to export Excel.')) from error

        output = self._build_work_checklist_xlsx(xlsxwriter)
        attachment = self.env['ir.attachment'].create({
            'name': 'Checklist A5 - %s.xlsx' % (self.name or ''),
            'type': 'binary',
            'datas': base64.b64encode(output),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Checklist A5')
        sheet.set_landscape()
        sheet.set_paper(9)
        sheet.fit_to_pages(1, 1)
        sheet.set_margins(left=0.2, right=0.2, top=0.25, bottom=0.25)
        sheet.set_column('A:A', 5)
        sheet.set_column('B:B', 16)
        sheet.set_column('C:C', 18)
        sheet.set_column('D:D', 11)
        sheet.set_column('E:E', 26)
        sheet.set_column('F:F', 18)
        sheet.set_column('G:G', 12)
        sheet.set_column('H:H', 12)
        sheet.set_column('I:I', 26)

        title_fmt = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 14, 'border': 1})
        header_fmt = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'text_wrap': True})
        label_fmt = workbook.add_format({'bold': True, 'border': 1, 'valign': 'vcenter', 'text_wrap': True})
        cell_fmt = workbook.add_format({'border': 1, 'valign': 'vcenter', 'text_wrap': True})
        center_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        section_fmt = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#EDEDED', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        sign_fmt = workbook.add_format({'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter'})

        clean = self._clean_print_text
        lot = self.stock_lot_id
        product = self.product_id or lot.product_id

        sheet.merge_range('A1:G2', 'CHECK LIST CÔNG VIỆC BẢO HÀNH, SỬA CHỮA', title_fmt)
        sheet.merge_range('H1:I2', 'BM-TE-113-000-003\nLần ban hành: 01', header_fmt)
        sheet.write('A3', 'Khách hàng', label_fmt)
        sheet.merge_range('B3:C3', clean(self.customer_id.name or self.owner_id.name), cell_fmt)
        sheet.write('D3', 'Địa chỉ', label_fmt)
        sheet.merge_range('E3:G3', clean(self.owner_address or self.delivery_address), cell_fmt)
        sheet.write('H3', 'Ngày nhận', label_fmt)
        sheet.write_datetime('I3', fields.Datetime.to_datetime(self.create_date), workbook.add_format({'border': 1, 'num_format': 'dd/mm/yyyy'}))

        sheet.write('A4', 'Liên hệ', label_fmt)
        sheet.merge_range('B4:C4', clean(self.owner_phone or self.customer_id.phone or self.customer_id.mobile), cell_fmt)
        sheet.write('D4', 'Model', label_fmt)
        sheet.merge_range('E4:F4', clean(product.display_name), cell_fmt)
        sheet.write('G4', 'Serial', label_fmt)
        sheet.write('H4', clean(lot.name), cell_fmt)
        sheet.write('I4', '', cell_fmt)

        sheet.write('A5', 'Hạn BH', label_fmt)
        if self.product_warranty_end_date:
            sheet.write_datetime('B5', fields.Datetime.to_datetime(self.product_warranty_end_date), workbook.add_format({'border': 1, 'num_format': 'dd/mm/yyyy'}))
        else:
            sheet.write('B5', '', cell_fmt)
        sheet.merge_range('C5:I5', 'Hiện trạng: %s' % clean(self.description or self.product_error_description), cell_fmt)

        headers = ['STT', 'Nội dung công việc', 'Phụ trách', 'Trạng thái', 'Bắt đầu', 'Kết thúc', 'Ghi chú']
        sheet.write_row('A6', headers[:1], section_fmt)
        sheet.merge_range('B6:C6', headers[1], section_fmt)
        sheet.write('D6', headers[2], section_fmt)
        sheet.write('E6', headers[3], section_fmt)
        sheet.write('F6', headers[4], section_fmt)
        sheet.write('G6', headers[5], section_fmt)
        sheet.merge_range('H6:I6', headers[6], section_fmt)

        row = 6
        date_fmt = workbook.add_format({'border': 1, 'num_format': 'dd/mm/yyyy'})
        for index, line in enumerate(self.checklist_ids, start=1):
            sheet.write(row, 0, index, center_fmt)
            sheet.merge_range(row, 1, row, 2, clean(line.name), cell_fmt)
            sheet.write(row, 3, clean(line.assigned_user_id.name), cell_fmt)
            sheet.write(row, 4, 'Hoàn thành' if line.is_done else '', cell_fmt)
            sheet.write(row, 5, '', cell_fmt)
            if line.done_date:
                sheet.write_datetime(row, 6, fields.Datetime.to_datetime(line.done_date), date_fmt)
            else:
                sheet.write(row, 6, '', cell_fmt)
            sheet.merge_range(row, 7, row, 8, clean(line.note), cell_fmt)
            row += 1

        if not self.checklist_ids:
            sheet.merge_range(row, 0, row, 8, 'Chưa có tác vụ/checklist.', cell_fmt)
            row += 1

        sheet.merge_range(row, 0, row + 2, 8, 'Kết quả kiểm tra:\n%s' % clean(self.survey_result_description or self.completed_task_description or self.implementation_work_note), cell_fmt)
        row += 3
        sheet.merge_range(row, 0, row + 2, 3, 'Nhân viên kiểm tra', sign_fmt)
        sheet.merge_range(row, 4, row + 2, 8, 'Người duyệt', sign_fmt)

        workbook.close()
        output.seek(0)
        attachment = self.env['ir.attachment'].create({
            'name': 'Checklist A5 - %s.xlsx' % (self.name or ''),
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def _build_work_checklist_xlsx(self, xlsxwriter):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        checkbox = chr(9744)
        clean = self._clean_print_text
        lot = self.stock_lot_id
        product = self.product_id or lot.product_id
        date_format = workbook.add_format({
            'border': 1, 'num_format': 'dd/mm/yy', 'font_size': 9,
            'align': 'center', 'valign': 'vcenter', 'shrink': True,
        })
        formats = {
            'logo': workbook.add_format({
                'bold': True, 'font_size': 22, 'font_color': '#00A3E0',
                'align': 'center', 'valign': 'vcenter',
            }),
            'slogan': workbook.add_format({
                'bold': True, 'italic': True, 'font_size': 14,
                'font_color': '#ED7D31',
                'align': 'left', 'valign': 'vcenter',
            }),
            'company': workbook.add_format({
                'bold': True, 'font_size': 13, 'font_color': '#5D6D7E',
                'align': 'center', 'valign': 'vcenter',
            }),
            'title': workbook.add_format({
                'bold': True, 'font_size': 12, 'font_color': '#FF0000',
                'align': 'center', 'valign': 'vcenter', 'border': 1,
            }),
            'code': workbook.add_format({
                'bold': True, 'font_size': 9, 'align': 'center',
                'valign': 'vcenter', 'border': 1, 'text_wrap': True,
            }),
            'label': workbook.add_format({
                'bold': True, 'border': 1, 'valign': 'vcenter',
                'text_wrap': True, 'font_size': 9, 'shrink': True,
            }),
            'section': workbook.add_format({
                'bold': True, 'border': 1, 'font_color': '#173B56',
                'bg_color': '#EAF4F8', 'align': 'left',
                'valign': 'vcenter', 'font_size': 10,
            }),
            'table_header': workbook.add_format({
                'bold': True, 'border': 1, 'font_color': '#173B56',
                'bg_color': '#F3F8FB', 'align': 'center',
                'valign': 'vcenter', 'font_size': 9, 'text_wrap': True,
            }),
            'cell': workbook.add_format({
                'border': 1, 'valign': 'vcenter', 'text_wrap': True,
                'font_size': 9, 'shrink': True,
            }),
            'center': workbook.add_format({
                'border': 1, 'align': 'center', 'valign': 'vcenter',
                'text_wrap': True, 'font_size': 9, 'shrink': True,
            }),
            'small_center': workbook.add_format({
                'border': 1, 'align': 'center', 'valign': 'vcenter',
                'font_size': 8, 'text_wrap': True,
            }),
            'dotted': workbook.add_format({
                'border': 1, 'bottom': 3, 'valign': 'top',
                'text_wrap': True, 'font_size': 9, 'shrink': True,
            }),
            'sign': workbook.add_format({
                'bold': True, 'border': 1, 'align': 'center',
                'valign': 'top', 'bg_color': '#F8FBFC',
            }),
        }

        self._write_work_checklist_front_sheet(workbook, formats, date_format, checkbox, clean, lot, product)
        self._write_work_checklist_back_sheet(workbook, formats, checkbox)
        workbook.close()
        output.seek(0)
        return output.read()

    def _setup_work_checklist_sheet(self, sheet):
        sheet.set_landscape()
        sheet.set_paper(11)
        sheet.fit_to_pages(1, 1)
        sheet.set_margins(left=0.12, right=0.12, top=0.15, bottom=0.15)
        sheet.center_horizontally()
        sheet.print_area(0, 0, 26, 8)
        sheet.set_zoom(85)
        sheet.hide_gridlines(2)
        sheet.set_column('A:A', 11)
        sheet.set_column('B:B', 13)
        sheet.set_column('C:C', 20)
        sheet.set_column('D:D', 11)
        sheet.set_column('E:E', 20)
        sheet.set_column('F:F', 13)
        sheet.set_column('G:G', 12)
        sheet.set_column('H:H', 12)
        sheet.set_column('I:I', 12)
        for row in range(0, 28):
            sheet.set_row(row, 18)

    def _write_work_checklist_header(self, sheet, formats):
        sheet.merge_range('A1:C1', '', formats['cell'])
        logo_path = self._get_dat_report_logo_path()
        if logo_path:
            sheet.insert_image(
                'A1',
                logo_path,
                {
                    'x_scale': 0.20,
                    'y_scale': 0.20,
                    'x_offset': 8,
                    'y_offset': 6,
                },
            )
        else:
            logo = self._get_dat_report_logo()
            if logo:
                sheet.insert_image(
                    'A1',
                    'dat_logo.png',
                    {
                        'image_data': io.BytesIO(base64.b64decode(logo)),
                        'x_scale': 0.20,
                        'y_scale': 0.20,
                        'x_offset': 8,
                        'y_offset': 6,
                    },
                )
            else:
                sheet.write('A1', 'DAT', formats['logo'])
        sheet.merge_range('D1:I1', 'CÔNG TY TNHH KỸ THUẬT ĐẠT', formats['company'])
        sheet.merge_range('A2:G2', 'CHECK LIST CÔNG VIỆC BẢO HÀNH, SỬA CHỮA', formats['title'])
        sheet.merge_range('H2:I2', 'BM-TE-113-000-003\nLần ban hành: 01', formats['code'])

    def _get_dat_report_logo_path(self):
        for filename in ('logo.png', 'dat-color.png'):
            logo_path = get_module_resource(
                'dat_website_helpdesk', 'static', 'src', 'img', filename
            )
            if logo_path:
                return logo_path
            module_root = os.path.dirname(os.path.dirname(__file__))
            custom_addons_root = os.path.dirname(module_root)
            logo_path = os.path.join(
                custom_addons_root,
                'dat_website_helpdesk',
                'static',
                'src',
                'img',
                filename,
            )
            if os.path.exists(logo_path):
                return logo_path
        return False

    def _get_dat_report_logo(self):
        self.ensure_one()
        companies = (
            getattr(self, 'branch', False),
            getattr(self, 'company_id', False),
            self.env.ref('base.main_company', raise_if_not_found=False),
            self.env.company,
        )
        for company in companies:
            if company and company.sudo().logo:
                return company.sudo().logo
        return False

    def _get_dat_report_logo_data_uri(self, company=False):
        logo = False
        companies = (
            company,
            getattr(self, 'branch', False),
            getattr(self, 'company_id', False),
            self.env.ref('base.main_company', raise_if_not_found=False),
            self.env.company,
        )
        for candidate in companies:
            if candidate and candidate.sudo().logo:
                logo = candidate.sudo().logo
                break

        if logo:
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

    def _write_work_checklist_front_sheet(self, workbook, formats, date_format, checkbox, clean, lot, product):
        sheet = workbook.add_worksheet('TRƯỚC')
        self._setup_work_checklist_sheet(sheet)
        sheet.set_row(0, 42)
        sheet.set_row(1, 24)
        for row in range(2, 6):
            sheet.set_row(row, 26)
        sheet.set_row(6, 22)
        sheet.set_row(7, 20)
        for row in range(8, 21):
            sheet.set_row(row, 20)
        sheet.set_row(21, 20)
        sheet.set_row(22, 24)
        sheet.set_row(23, 24)
        sheet.set_row(24, 24)
        sheet.set_row(25, 24)
        sheet.set_row(26, 22)
        self._write_work_checklist_header(sheet, formats)

        customer_name = clean(self._service_owner_company_name())
        contact_name = clean(self._service_contact_name())
        contact_phone = clean(self._service_contact_phone())
        product_name = clean(product.display_name if product else '')
        serial_name = clean(lot.name if lot else '')

        sheet.write('A3', 'Khách hàng', formats['label'])
        sheet.merge_range('B3:E3', customer_name, formats['cell'])
        sheet.write('F3', 'Ngày nhận', formats['label'])
        sheet.write_datetime('G3', fields.Datetime.to_datetime(self.create_date), date_format)
        sheet.write('H3', 'Người nhận', formats['label'])
        sheet.write('I3', '', formats['cell'])

        sheet.write('A4', 'Liên hệ', formats['label'])
        sheet.merge_range('B4:C4', contact_name, formats['cell'])
        sheet.write('D4', 'SĐT', formats['label'])
        sheet.write('E4', contact_phone, formats['cell'])
        sheet.write('F4', 'Người đem về (NVGH/ Khách):', formats['label'])
        sheet.merge_range('G4:I4', '', formats['cell'])

        sheet.write('A5', 'Model:', formats['label'])
        sheet.merge_range('B5:C5', product_name, formats['cell'])
        sheet.write('D5', 'Serial:', formats['label'])
        sheet.write('E5', serial_name, formats['cell'])
        sheet.write('F5', 'Phí', formats['label'])
        sheet.write('G5', 'Khách trả %s' % checkbox, formats['small_center'])
        sheet.write('H5', 'DAT trả %s' % checkbox, formats['small_center'])
        sheet.write('I5', '', formats['cell'])

        sheet.write('A6', 'Hạn bảo hành', formats['label'])
        if self.product_warranty_end_date:
            sheet.write_datetime('B6', fields.Datetime.to_datetime(self.product_warranty_end_date), date_format)
        else:
            sheet.write('B6', '', formats['cell'])
        sheet.write('C6', '', formats['cell'])
        sheet.write('D6', 'Photo:', formats['label'])
        sheet.write('E6', '', formats['cell'])
        sheet.write('F6', 'Ngày trả', formats['label'])
        sheet.write('G6', '', formats['cell'])
        sheet.write('H6', 'Người trả', formats['label'])
        sheet.write('I6', '', formats['cell'])

        status_text = 'Hiện trạng: K thùng %s  K nắp %s  K chặn %s  K quạt %s  K keypad %s  BHTX %s' % (
            checkbox, checkbox, checkbox, checkbox, checkbox, checkbox
        )
        sheet.merge_range('A7:E7', status_text, formats['label'])
        sheet.merge_range('F7:G7', 'Kiểm tra bo mạch', formats['center'])
        sheet.write('H7', 'Test nguội', formats['center'])
        sheet.write('I7', 'Test có tải', formats['center'])

        sheet.write('A8', 'Thiết bị', formats['center'])
        sheet.merge_range('B8:C8', 'Số Serial', formats['center'])
        sheet.merge_range('D8:E8', 'Mã', formats['center'])
        sheet.write('F8', 'SL', formats['center'])
        sheet.write('G8', 'Fault', formats['center'])
        sheet.write('H8', 'Normal\nV', formats['center'])
        sheet.write('I8', 'V', formats['center'])

        devices = ['Bo ĐK', 'Bo I/O', 'Bo CS', 'Bo Tụ', 'Bo Nguồn', 'Bo Hall', 'Rectifier', 'Igbt', 'Quạt']
        for row, device in enumerate(devices, start=8):
            sheet.write(row, 0, device, formats['cell'])
            sheet.merge_range(row, 1, row, 2, '', formats['cell'])
            sheet.merge_range(row, 3, row, 4, '', formats['cell'])
            sheet.write(row, 5, '', formats['center'])
            sheet.write(row, 6, '', formats['center'])
            sheet.write(row, 7, '', formats['center'])
            sheet.write(row, 8, '', formats['center'])
        for row in range(17, 21):
            sheet.write(row, 0, '', formats['cell'])
            sheet.merge_range(row, 1, row, 2, '', formats['cell'])
            sheet.merge_range(row, 3, row, 4, '', formats['cell'])
            for column in range(5, 9):
                sheet.write(row, column, '', formats['center'])

        result_text = clean(
            self.survey_result_description
            or self.completed_task_description
            or self.implementation_work_note
            or self.description
            or self.product_error_description
        )
        sheet.merge_range('A22:G22', 'Kết quả kiểm tra:', formats['label'])
        sheet.merge_range('A23:G24', result_text, formats['dotted'])
        sheet.merge_range('A25:G26', '', formats['dotted'])
        sheet.merge_range('H22:I26', 'Nhân Viên', formats['sign'])
        sheet.write('A27', 'VS Sơ Bộ %s' % checkbox, formats['label'])
        sheet.write('B27', 'BHBM %s' % checkbox, formats['label'])
        sheet.merge_range('C27:D27', 'Không sửa chữa %s' % checkbox, formats['label'])
        sheet.write('E27', 'Chờ báo giá %s' % checkbox, formats['label'])
        sheet.write('F27', 'Hoàn thành %s' % checkbox, formats['label'])
        sheet.merge_range('G27:I27', 'Người lấy (NVGH/ Khách):', formats['label'])

    def _write_work_checklist_back_sheet(self, workbook, formats, checkbox):
        sheet = workbook.add_worksheet('SAU')
        self._setup_work_checklist_sheet(sheet)
        sheet.print_area(0, 0, 26, 8)
        sheet.set_row(0, 42)
        sheet.set_row(1, 24)
        self._write_work_checklist_header(sheet, formats)
        sheet.set_row(2, 22)
        sheet.set_row(3, 22)
        sheet.set_row(8, 22)
        sheet.set_row(13, 22)
        sheet.set_row(20, 22)
        sheet.merge_range('A3:I3', 'Lịch sử lỗi', formats['section'])
        sheet.write('A4', 'Lần', formats['table_header'])
        sheet.merge_range('B4:C4', 'Chế độ chạy', formats['table_header'])
        sheet.merge_range('D4:E4', 'Mô tả lỗi', formats['table_header'])
        sheet.merge_range('F4:G4', 'Ngày phát sinh', formats['table_header'])
        sheet.merge_range('H4:I4', 'Ghi chú', formats['table_header'])
        for row in range(4, 7):
            sheet.write(row, 0, 'Lần %s' % (row - 3), formats['center'])
            sheet.merge_range(row, 1, row, 2, '', formats['cell'])
            sheet.merge_range(row, 3, row, 4, '', formats['cell'])
            sheet.merge_range(row, 5, row, 6, '', formats['cell'])
            sheet.merge_range(row, 7, row, 8, '', formats['cell'])

        sheet.merge_range('A8:I8', 'Thông tin lỗi', formats['section'])
        sheet.write_row('A9', ['Lần', 'Hz', 'A', 'V bus', 'Input', 'Output', 'Load', 'Nhiệt độ', 'Ghi chú'], formats['table_header'])
        for row in range(9, 12):
            sheet.write(row, 0, 'Lần %s' % (row - 8), formats['center'])
            for column in range(1, 9):
                sheet.write(row, column, '', formats['cell'])

        sheet.merge_range('A13:I13', 'Thông số đặc biệt', formats['section'])
        sheet.merge_range('A14:C14', 'Initial checking', formats['table_header'])
        sheet.merge_range('D14:F14', 'Terminal/Input/Output', formats['table_header'])
        sheet.merge_range('G14:I14', 'Ghi chú', formats['table_header'])
        for row in range(14, 19):
            sheet.merge_range(row, 0, row, 2, '', formats['cell'])
            sheet.merge_range(row, 3, row, 5, '', formats['cell'])
            sheet.merge_range(row, 6, row, 8, '', formats['cell'])

        sheet.merge_range('A20:I20', 'Kiểm tra pha', formats['section'])
        sheet.write_row('A21', ['R', 'S', 'T', 'U', 'V', 'W', '+', '-', 'Ghi chú'], formats['table_header'])
        for row in range(21, 24):
            for column in range(0, 9):
                sheet.write(row, column, '', formats['cell'])

        sheet.merge_range(
            'A25:F27',
            'Đề xuất báo giá/bảo hành: %s\nBảo hành %s  Báo giá %s  Hoàn thành %s' % (
                '', checkbox, checkbox, checkbox
            ),
            formats['cell'],
        )
        sheet.merge_range('G25:H27', 'Nhân Viên Kiểm Tra', formats['sign'])
        sheet.merge_range('I25:I27', 'Người Duyệt', formats['sign'])

    def action_create_sap_so_from_ticket(self):
        for ticket in self:
            order = ticket.sale_order_ids.filtered(
                lambda so: not (so.sap_status or '').strip()
                and (
                    so.sap_is_create_so
                    if 'sap_is_create_so' in so._fields
                    else True
                )
            )[:1]
            if not order:
                raise UserError(_('Ticket %s has no quotation ready to create SAP SO.') % (ticket.name or ''))
            so_number = order.create_sap_doc(doc_type='SO')
            if so_number:
                ticket.sap_sale_order_number = so_number
                message = _('T\u1ea1o SO SAP th\u00e0nh c\u00f4ng: %s') % so_number
                if hasattr(ticket, '_message_log_batch'):
                    ticket._message_log_batch(bodies={ticket.id: message})
                else:
                    ticket.message_post(body=message)
                if 'popup_notification' in ticket._fields:
                    ticket.popup_notification = message
        return True
