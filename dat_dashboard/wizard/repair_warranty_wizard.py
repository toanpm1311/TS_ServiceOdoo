# -*- coding: utf-8 -*-
import io
import base64
from odoo import api, fields, models, _
from xlsxwriter import Workbook
from ..models.common_utils_mixin import CommonUtilsMixin

class RepairWarrantyReportWizardLine(models.TransientModel):
    _name = 'repair.warranty.report.wizard.line'
    _description = 'Repair Warranty Report Wizard Line'

    wizard_id               = fields.Many2one(
        'repair.warranty.report.wizard', ondelete='cascade',
    )
    sequence                = fields.Integer('No.', readonly=True)
    ticket_id               = fields.Many2one(
        'ticket.helpdesk', 'Request Code', readonly=True,
    )
    customer_id             = fields.Many2one(
        'res.partner', 'Customer', readonly=True,
    )
    saleperson_id           = fields.Many2one(
        'hr.employee', 'Salesperson', readonly=True,
    )
    sap_business_unit       = fields.Char('Business Unit', readonly=True)
    product_id              = fields.Many2one('product.product', 'Item Code', readonly=True)
    stock_lot_id = fields.Many2one('stock.lot', string='Serial Number', readonly=True)
    create_date             = fields.Datetime('Create Date', readonly=True)
    status = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
        ('on_hold', 'On Hold')], default='new', readonly=False)
    priority_id           = fields.Many2one('ticket.priority','Priority',readonly=True)
    ticket_type_id        = fields.Many2one('helpdesk.type','Request Type',readonly=True)
    step_id               = fields.Many2one('ticket.step','Current Step',readonly=True)
    assigned_user_id      = fields.Many2one('res.users','Assignee', readonly=True)
    product_warranty_status = fields.Selection([('warranty', 'Warranty'), ('out_of_warranty', 'Out of Warranty'),
                                                ('not_eligible_for_warranty', 'Not eligible for warranty')],
                                               string='Product Warranty Status',readonly=True)
    status_after_repair = fields.Char(string='Status After Repair')
    service_action = fields.Selection([
        ('warranty_at_dat', 'Warranty At DAT'),
        ('repair_at_dat', 'Repair At DAT (Paid)'),
        ('warranty_onsite', 'Warranty Onsite'),
        ('repair_onsite', 'Repair Onsite (Paid)'),
        ('warranty_at_dat_paid', 'Warranty At DAT (Paid)'),
        ('warranty_onsite_paid', 'Warranty Onsite (Paid)'),
        ('online_technical_support', 'Online Technical Support'),
        ('new_installation_onsite', 'New installation Onsite'),
        ('request_return', 'Request Return'),
        ('onsite_technical_support', 'Onsite Technical Support')], string='Solution', readonly=True)
    warranty_service_type = fields.Selection([
        ('repair', 'Repair'),
        ('replace', 'Replace'),
        ('replace_with_new_board', 'Replace with new board'),
        ('replace_with_old_board', 'Replace with old board'),
        ('clean_and_load_test', 'Clean & load test'),
    ], string='Warranty Service Type', readonly=True)
    branch             = fields.Many2one('res.company','Branch',readonly=True)
    total_time_spent      = fields.Float('Time To Finish',readonly=True)
    is_warranty_remote = fields.Selection(
        [('Yes', 'Yes'), ('No', 'No')],
        string='Is Warranty Remote',
        readonly=True
    )
    request_return_reason = fields.Text('Reason Return',readonly=True)

class RepairWarrantyReportWizard(models.TransientModel, CommonUtilsMixin):
    _name = 'repair.warranty.report.wizard'
    _description = 'Repair Warranty Data Report'

    date_from     = fields.Date('Create Date From')
    date_to       = fields.Date('Create Date To')
    request_code  = fields.Char('Request Code')
    customer_id   = fields.Many2one('res.partner', 'Customer')
    engineer_id   = fields.Many2one('res.users', 'Engineer')
    branch_id     = fields.Many2one('res.company', 'Branch',
                             domain=lambda self: [('id', 'in', self.env.ref('base.main_company').child_ids.ids)])
    business_unit = fields.Char('Business Unit')

    line_ids = fields.One2many(
        'repair.warranty.report.wizard.line',
        'wizard_id',
        string='Lines',
        compute='_compute_lines',
        readonly=True,
        store=True,
    )

    @api.depends('date_from', 'date_to', 'request_code',
                 'customer_id', 'engineer_id', 'branch_id', 'business_unit')
    def _compute_lines(self):
        type_refs = [
            'dat_website_helpdesk.ticket_type_1',
            'dat_website_helpdesk.ticket_type_2',
            'dat_website_helpdesk.ticket_type_3',
            'dat_website_helpdesk.ticket_type_4',
        ]
        type_ids = [
            self.env.ref(ref).id
            for ref in type_refs
            if self.env.ref(ref, raise_if_not_found=False)
        ]
        for wiz in self:
            wiz.line_ids = [(5, 0, 0)]
            domain = [('ticket_type_id', 'in', type_ids)]
            if wiz.date_from:      domain.append(('create_date', '>=', wiz.date_from))
            if wiz.date_to:        domain.append(('create_date', '<=', wiz.date_to))
            if wiz.request_code:   domain.append(('name', 'ilike', wiz.request_code))
            if wiz.customer_id:    domain.append(('customer_id', '=', wiz.customer_id.id))
            if wiz.engineer_id:    domain.append(('assigned_user_ids', 'in', [wiz.engineer_id.id]))
            if wiz.branch_id:      domain.append(('branch', '=', wiz.branch_id.id))
            if wiz.business_unit:  domain.append(('sap_business_unit', 'ilike', wiz.business_unit))
            tickets = self.env['ticket.helpdesk'].search(domain, order='create_date desc')
            lines = []
            for idx, t in enumerate(tickets, start=1):
                lines.append((0, 0, {
                    'sequence': idx,
                    'ticket_id': t.id,
                    'customer_id': t.customer_id.id,
                    'saleperson_id': t.saleperson_id.id,
                    'sap_business_unit': t.sap_business_unit,
                    'product_id': t.product_id.id if t.product_id else False,
                    'stock_lot_id': t.stock_lot_id.id if t.stock_lot_id else False,
                    'create_date': t.create_date,
                    'status': t.status,
                    'priority_id': t.priority_id.id,
                    'ticket_type_id': t.ticket_type_id.id,
                    'step_id': t.step_id.id,
                    'assigned_user_id': t.assigned_user_id.id if t.assigned_user_id else False,
                    'product_warranty_status': t.product_warranty_status,
                    'status_after_repair': t.status_after_repair,
                    'service_action': t.service_action,
                    'warranty_service_type': t.warranty_service_type,
                    'branch': t.branch.id,
                    'total_time_spent': t.total_time_spent,
                    'is_warranty_remote': 'Yes' if t.is_warranty_remote else 'No',
                    'request_return_reason': t.request_return_reason,
                }))
            wiz.line_ids = lines

    def _compute_display_name(self):
        for record in self:
            record.display_name = _("Repair Warranty Data Report")

    @api.model
    def create(self, vals):
        records = super().create(vals)
        records._compute_lines()
        return records

    def action_export_xlsx(self):
        self.ensure_one()
        headers = [
            _('Request Code'),          # name
            _('Customer'),              # customer_id
            _('Salesperson'),           # saleperson_id
            _('Business Unit'),         # sap_business_unit
            _('Item Code'),             # product_id / product_code
            _('Serial Number'),         # stock_lot_id
            _('Create Date'),           # create_date
            _('Status'),                # status
            _('Priority'),              # priority_id
            _('Request Type'),          # ticket_type_id
            _('Current Step'),          # step_id
            _('Assigned User'),         # assigned_user_id
            _('Warranty Status'),       # product_warranty_status
            _('Status After Repair'),   # status_after_repair
            _('Warranty Remote'),       # service_action
            _('Service Action'),        # warranty_service_type
            _('Branch'),                # branch
            _('Time To Finish'),        # total_time_spent
            _('Resolution'),            # service_action
            _('Reason Return'),         # request_return_reason
        ]

        output = io.BytesIO()
        wb = Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('Report')
        ws.set_column(0, len(headers) - 1, 18)
        filters = [
            (_('Create Date From'), self.date_from.strftime('%d/%m/%Y') if self.date_from else ''),
            (_('Create Date To'), self.date_to.strftime('%d/%m/%Y') if self.date_to else ''),
            (_('Request Code'), self.request_code or ''),
            (_('Customer'), self.customer_id.display_name or ''),
            (_('Engineer'), self.engineer_id.display_name or ''),
            (_('Branch'), self.branch_id.display_name or ''),
            (_('Business Unit'), self.business_unit or ''),
        ]
        header_row, header_format = self._write_xlsx_report_header(
            wb, ws, _('Repair Warranty Data Report'), len(headers), filters
        )

        for col, heading in enumerate(headers):
            ws.write(header_row, col, heading, header_format)

        self.write_data_into_xlsx_file(ws, header_row + 1)

        wb.close()
        output.seek(0)
        data = output.read()

        attachment = self.env['ir.attachment'].create({
            'name': 'repair_warranty_report.xlsx',
            'datas': base64.b64encode(data),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def write_data_into_xlsx_file(self, ws, start_row=1):
        for row_idx, rec in enumerate(self.line_ids, start=start_row):
            for col_idx, value in enumerate(self._get_row_values(rec)):
                ws.write(row_idx, col_idx, value)

    def _get_row_values(self, rec):
        """
        Extract all the little formatting bits from the main method
        so that write_data_into_xlsx_file has almost no logic in it.
        """
        create_date = (
            rec.create_date.strftime('%Y-%m-%d %H:%M:%S')
            if rec.create_date
            else ''
        )

        status_label = self.get_record_selection_label(rec, 'status')
        product_warranty_status_label = self.get_record_selection_label(rec, 'product_warranty_status')
        warranty_service_type_label = self.get_record_selection_label(rec, 'warranty_service_type')
        service_action_label = self.get_record_selection_label(rec, 'service_action')
        total_time_spent_label = self.float_to_time_string(rec.total_time_spent)

        is_warranty_remote_label = (
            _('Yes') if rec.is_warranty_remote == 'Yes' else _('No')
        )

        return [
            rec.ticket_id.name or '',
            rec.customer_id.name or '',
            rec.saleperson_id.name or '',
            rec.sap_business_unit or '',
            rec.product_id.display_name or '',
            rec.stock_lot_id.name or '',
            create_date,
            status_label,
            rec.priority_id.name or '',
            rec.ticket_type_id.name or '',
            rec.step_id.name or '',
            rec.assigned_user_id.name,
            product_warranty_status_label,
            rec.status_after_repair or '',
            is_warranty_remote_label,
            warranty_service_type_label,
            rec.branch.name or '',
            total_time_spent_label,
            service_action_label,
            rec.request_return_reason or '',
        ]
