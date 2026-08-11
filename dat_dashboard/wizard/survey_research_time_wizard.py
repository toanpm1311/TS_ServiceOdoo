# -*- coding: utf-8 -*-
import io
import base64
from odoo import api, fields, models, _
from xlsxwriter import Workbook
from ..models.common_utils_mixin import CommonUtilsMixin

class SurveyResearchTimeWizardLine(models.TransientModel):
    _name = 'survey.research.time.wizard.line'
    _description = 'Survey & Research Time Wizard Line'

    wizard_id          = fields.Many2one('survey.research.time.wizard', ondelete='cascade')
    sequence           = fields.Integer('No.', readonly=True)
    create_date        = fields.Date('Date', readonly=True)
    user_id            = fields.Many2one('res.users', 'User', readonly=True)
    employee_id        = fields.Many2one('hr.employee', 'Employee', readonly=True)
    department_name    = fields.Char('Department',       readonly=True)
    ticket_id          = fields.Many2one('ticket.helpdesk','Ticket',   readonly=True)
    company_id         = fields.Many2one('res.company',  'Branch',    readonly=True)
    total_time_spent   = fields.Float('Total Time (h)',  readonly=True)

class SurveyResearchTimeWizard(models.TransientModel, CommonUtilsMixin):
    _name = 'survey.research.time.wizard'
    _description = 'Total Time Survey & Research Steps Report Wizard'

    date_from        = fields.Date('From Date')
    date_to          = fields.Date('To Date')
    user_id          = fields.Many2one('res.users',    'Employee')
    department_name  = fields.Char('Department')
    ticket_id        = fields.Many2one('ticket.helpdesk','Ticket')
    company_id       = fields.Many2one(
        'res.company', 'Branch',
        domain=lambda self: [('id','in', self.env.ref('base.main_company').child_ids.ids)]
    )

    line_ids = fields.One2many(
        'survey.research.time.wizard.line',
        'wizard_id',
        string='Report Lines',
        compute='_compute_lines',
        readonly=True,
        store=True,
    )

    @api.depends('date_from', 'date_to', 'user_id', 'department_name', 'ticket_id', 'company_id')
    def _compute_lines(self):
        for wiz in self:
            wiz.line_ids = [(5, 0, 0)]
            dom = []
            if wiz.date_from:       dom.append(('create_date', '>=', wiz.date_from))
            if wiz.date_to:         dom.append(('create_date', '<=', wiz.date_to))
            if wiz.user_id:        dom.append(('user_id', '=', wiz.user_id.id))
            if wiz.department_name: dom.append(('department_name', 'ilike', wiz.department_name))
            if wiz.ticket_id:      dom.append(('ticket_id', '=', wiz.ticket_id.id))
            if wiz.company_id:     dom.append(('company_id', '=', wiz.company_id.id))
            recs = self.env['survey.research.time.report'].search(dom, order='total_time_spent desc')
            lines = []
            for idx, rec in enumerate(recs, start=1):
                lines.append((0, 0, {
                    'sequence': idx,
                    'user_id': rec.user_id.id,
                    'create_date': rec.create_date,
                    'employee_id': rec.employee_id.id,
                    'department_name': rec.department_name,
                    'ticket_id': rec.ticket_id.id,
                    'company_id': rec.company_id.id,
                    'total_time_spent': rec.total_time_spent,
                }))
            wiz.line_ids = lines

    def _compute_display_name(self):
        for record in self:
            record.display_name = _("Total Time Survey & Research Steps Report Wizard")

    def action_export_xlsx(self):
        self.ensure_one()
        headers = [
            _('Employee'),
            _('Department'),
            _('Ticket'),
            _('Branch'),
            _('Total Time'),
        ]
        output = io.BytesIO()
        wb = Workbook(output, {'in_memory': True})
        sheet = wb.add_worksheet(_('Survey & Research Time'))
        sheet.set_column(0, len(headers) - 1, 22)
        filters = [
            (_('From Date'), self.date_from.strftime('%d/%m/%Y') if self.date_from else ''),
            (_('To Date'), self.date_to.strftime('%d/%m/%Y') if self.date_to else ''),
            (_('Employee'), self.user_id.display_name or ''),
            (_('Department'), self.department_name or ''),
            (_('Ticket'), self.ticket_id.name or ''),
            (_('Branch'), self.company_id.display_name or ''),
        ]
        header_row, header_format = self._write_xlsx_report_header(
            wb, sheet, _('Survey and Research Time Report'), len(headers), filters
        )

        # write headers
        for c, h in enumerate(headers):
            sheet.write(header_row, c, h, header_format)

        # write rows
        for r, rec in enumerate(self.line_ids, start=header_row + 1):
            total_time_spent_label = self.float_to_time_string(rec.total_time_spent)
            row = [
                rec.user_id.name or '',
                rec.department_name or '',
                rec.ticket_id.name or '',
                rec.company_id.name or '',
                total_time_spent_label,
            ]
            for c, val in enumerate(row):
                sheet.write(r, c, val)

        wb.close()
        data = output.getvalue()
        fname = _('Survey_Research_Time_Report.xlsx')
        attachment = self.env['ir.attachment'].create({
            'name': fname,
            'datas': base64.b64encode(data),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true&filename={fname}',
            'target': 'new',
        }
