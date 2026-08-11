# -*- coding: utf-8 -*-
import io
import base64
from odoo import api, fields, models, _
from xlsxwriter import Workbook
from ..models.common_utils_mixin import CommonUtilsMixin

class SolutionDesignPointsWizardLine(models.TransientModel):
    _name = 'solution.design.points.wizard.line'
    _description = 'Solution Design Points Wizard Line'

    wizard_id        = fields.Many2one(
        'solution.design.points.wizard', ondelete='cascade', required=True
    )
    sequence         = fields.Integer('No.', readonly=True)
    user_id          = fields.Many2one('res.users',    'User',       readonly=True)
    create_date      = fields.Date    ('Date',       readonly=True)
    employee_id      = fields.Many2one('hr.employee','Employee',   readonly=True)
    department_name  = fields.Char    ('Department', readonly=True)
    company_id       = fields.Many2one('res.company','Branch',     readonly=True)
    total_score      = fields.Float   ('Total Score',readonly=True)

class SolutionDesignPointsWizard(models.TransientModel, CommonUtilsMixin):
    _name = 'solution.design.points.wizard'
    _description = 'Solution Design Points Report Wizard'

    date_from = fields.Date('From Date')
    date_to = fields.Date('To Date')
    employee_id     = fields.Many2one('hr.employee', 'Employee')
    department_name = fields.Char(                'Department')
    company_id      = fields.Many2one(
        'res.company', 'Branch',
        domain=lambda self: [('id', 'in', self.env.ref('base.main_company').child_ids.ids)]
    )

    line_ids = fields.One2many(
        'solution.design.points.wizard.line',
        'wizard_id',
        string='Report Lines',
        compute='_compute_lines',
        readonly=True,
        store=True,
    )

    @api.depends('date_from', 'date_to', 'employee_id', 'department_name', 'company_id')
    def _compute_lines(self):
        report = self.env['solution.design.points.report']
        for wiz in self:
            wiz.line_ids = [(5, 0, 0)]
            dom = []
            if wiz.date_from:       dom.append(('create_date', '>=', wiz.date_from))
            if wiz.date_to:         dom.append(('create_date', '<=', wiz.date_to))
            if wiz.employee_id:     dom.append(('employee_id', '=', wiz.employee_id.id))
            if wiz.department_name: dom.append(('department_name', 'ilike', wiz.department_name))
            if wiz.company_id:      dom.append(('company_id', '=', wiz.company_id.id))
            recs = report.search(dom, order='total_score desc, create_date desc')
            lines = []
            for idx, rec in enumerate(recs, start=1):
                lines.append((0, 0, {
                    'sequence': idx,
                    'user_id': rec.user_id.id,
                    'create_date': rec.create_date,
                    'employee_id': rec.employee_id.id,
                    'department_name': rec.department_name,
                    'company_id': rec.company_id.id,
                    'total_score': rec.total_score,
                }))
            wiz.line_ids = lines

    def _compute_display_name(self):
        for record in self:
            record.display_name = _("Solution Design Points Report Wizard")

    def action_export_xlsx(self):
        self.ensure_one()
        headers = [
            _('Employee'),
            _('Department'),
            _('Branch'),
            _('Total Score'),
        ]
        output = io.BytesIO()
        wb = Workbook(output, {'in_memory': True})
        sheet = wb.add_worksheet(_('Solution Design Points'))
        sheet.set_column(0, len(headers) - 1, 22)
        filters = [
            (_('From Date'), self.date_from.strftime('%d/%m/%Y') if self.date_from else ''),
            (_('To Date'), self.date_to.strftime('%d/%m/%Y') if self.date_to else ''),
            (_('Employee'), self.employee_id.display_name or ''),
            (_('Department'), self.department_name or ''),
            (_('Branch'), self.company_id.display_name or ''),
        ]
        header_row, header_format = self._write_xlsx_report_header(
            wb, sheet, _('Solution Design Points Report'), len(headers), filters
        )

        for c, h in enumerate(headers):
            sheet.write(header_row, c, h, header_format)

        for r, rec in enumerate(self.line_ids, start=header_row + 1):
            row = [
                rec.employee_id.name or '',
                rec.department_name   or '',
                rec.company_id.name   or '',
                rec.total_score,
            ]
            for c, v in enumerate(row):
                sheet.write(r, c, v)

        wb.close()
        data = output.getvalue()
        fname = _('Solution_Design_Points_Report.xlsx')
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
