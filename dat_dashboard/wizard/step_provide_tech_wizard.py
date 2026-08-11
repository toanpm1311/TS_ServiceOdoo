import io
import base64
from odoo import api, fields, models, _
from xlsxwriter import Workbook
from ..models.common_utils_mixin import CommonUtilsMixin

class StepProvideTechWizardLine(models.TransientModel):
    _name = 'step.provide.tech.wizard.line'
    _description = 'Provide Tech Solutions Step Report Wizard Line'

    wizard_id        = fields.Many2one(
        'step.provide.tech.wizard', ondelete='cascade',
        string='Wizard', required=True,
    )
    sequence         = fields.Integer('No.', readonly=True)
    user_id          = fields.Many2one('res.users',    'User',      readonly=True)
    create_date      = fields.Date    ('Date',         readonly=True)
    employee_id      = fields.Many2one('hr.employee','Employee',   readonly=True)
    department_name  = fields.Char    ('Department',   readonly=True)
    company_id       = fields.Many2one('res.company','Company',    readonly=True)
    step_count       = fields.Integer ('Count',        readonly=True)

class StepProvideTechWizard(models.TransientModel, CommonUtilsMixin):
    _name = 'step.provide.tech.wizard'
    _description = 'Provide Tech Solutions Step Report Wizard'

    date_from = fields.Date('From Date')
    date_to = fields.Date('To Date')
    employee_id   = fields.Many2one('hr.employee',   'Employee')
    department_name = fields.Char('Department')
    company_id    = fields.Many2one('res.company',   'Company',
                             domain=lambda self: [('id', 'in', self.env.ref('base.main_company').child_ids.ids)])

    line_ids = fields.One2many(
        'step.provide.tech.wizard.line',
        'wizard_id',
        string='Report Lines',
        compute='_compute_lines',
        readonly=True,
        store=True,
    )

    @api.depends('date_from', 'date_to', 'employee_id', 'department_name', 'company_id')
    def _compute_lines(self):
        report = self.env['step.provide.tech.report']
        for wiz in self:
            wiz.line_ids = [(5, 0, 0)]
            dom = []
            if wiz.date_from:       dom.append(('create_date', '>=', wiz.date_from))
            if wiz.date_to:         dom.append(('create_date', '<=', wiz.date_to))
            if wiz.employee_id:     dom.append(('employee_id', '=', wiz.employee_id.id))
            if wiz.department_name: dom.append(('department_name', 'ilike', wiz.department_name))
            if wiz.company_id:      dom.append(('company_id', '=', wiz.company_id.id))
            recs = report.search(dom, order='create_date desc, step_count desc')
            lines = [
                (0, 0, {
                    'sequence': idx,
                    'user_id': rec.user_id.id,
                    'create_date': rec.create_date,
                    'employee_id': rec.employee_id.id,
                    'department_name': rec.department_name,
                    'company_id': rec.company_id.id,
                    'step_count': rec.step_count,
                })
                for idx, rec in enumerate(recs, start=1)
            ]
            wiz.line_ids = lines

    def _compute_display_name(self):
        for record in self:
            record.display_name = _("Provide Tech Solutions Step Report Wizard")

    def action_export_xlsx(self):
        self.ensure_one()

        headers = [
            _('Employee'),
            _('Department'),
            _('Company'),
            _('Count'),
        ]

        output = io.BytesIO()
        workbook = Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(_('Provide Tech Report'))
        sheet.set_column(0, len(headers) - 1, 22)
        filters = [
            (_('From Date'), self.date_from.strftime('%d/%m/%Y') if self.date_from else ''),
            (_('To Date'), self.date_to.strftime('%d/%m/%Y') if self.date_to else ''),
            (_('Employee'), self.employee_id.display_name or ''),
            (_('Department'), self.department_name or ''),
            (_('Company'), self.company_id.display_name or ''),
        ]
        header_row, header_format = self._write_xlsx_report_header(
            workbook, sheet, _('Provide Tech Solutions Step Report'), len(headers), filters
        )

        for col_idx, title in enumerate(headers):
            sheet.write(header_row, col_idx, title, header_format)

        for row_idx, rec in enumerate(self.line_ids, start=header_row + 1):
            row = [
                rec.employee_id.name or '',
                rec.department_name or '',
                rec.company_id.name or '',
                rec.step_count,
            ]
            for col_idx, val in enumerate(row):
                sheet.write(row_idx, col_idx, val)

        workbook.close()
        output.seek(0)
        data = output.read()

        filename = _('Provide_Tech_Solutions_Report.xlsx')
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(data),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true&filename={filename}',
            'target': 'new',
        }
