# -*- coding: utf-8 -*-
import io
import base64
from odoo import api, fields, models, _
from xlsxwriter import Workbook
from ..models.common_utils_mixin import CommonUtilsMixin

class StepSlaComplianceWizardLine(models.TransientModel):
    _name = 'step.sla.compliance.wizard.line'
    _description = 'SLA Compliance Wizard Line'

    wizard_id    = fields.Many2one(
        'step.sla.compliance.wizard', ondelete='cascade', required=True
    )
    sequence     = fields.Integer('No.', readonly=True)
    ticket_id    = fields.Many2one('ticket.helpdesk', 'Ticket',       readonly=True)
    create_date  = fields.Date(         'Ticket Date',                          readonly=True)
    customer_id  = fields.Many2one('res.partner',      'Customer', readonly=True)
    request_type = fields.Many2one('helpdesk.type',    'Request Type',readonly=True)
    priority_id  = fields.Many2one('ticket.priority',  'Priority',    readonly=True)
    engineer_id  = fields.Many2one('res.users',        'Engineer',    readonly=True)
    step_id      = fields.Many2one('ticket.step',      'Step Name',   readonly=True)
    start_date   = fields.Datetime(     'Step Start',                          readonly=True)
    end_date     = fields.Datetime(     'Step End',                            readonly=True)
    time_sla     = fields.Float(        'SLA (h)',                             readonly=True)
    time_spent   = fields.Float(        'Actual (h)',                          readonly=True)
    difference   = fields.Float(        'Difference (h)',                      readonly=True)
    sla_status   = fields.Char(         'SLA Status',                          readonly=True)
    company_id   = fields.Many2one('res.company','Branch',             readonly=True)

class StepSlaComplianceWizard(models.TransientModel, CommonUtilsMixin):
    _name = 'step.sla.compliance.wizard'
    _description = 'SLA Compliance Detail Report Wizard'

    SLA_STAGE_RULES = [
        (1, 'Giai đoạn Báo giá - Chuẩn bị', '2-1'),
        (2, 'Giai đoạn Chuẩn bị - Duyệt đơn', '3-2'),
        (3, 'Giai đoạn Báo giá - Duyệt đơn', '3-1'),
        (4, 'Giai đoạn SM Duyệt giá', '4-3'),
        (5, 'Giai đoạn BU Duyệt giá', '5-4'),
        (6, 'Giai đoạn Kế toán Duyệt công nợ', '6-5'),
        (7, 'Giai đoạn Điều vận Xuất kho', '7-6'),
        (8, 'Giai đoạn Kho xuất hàng', '8-7'),
        (9, 'Giai đoạn Điều vận Xếp xe', '9-7 (nếu có 9), 10-7 (nếu không có 9)'),
        (10, 'Giai đoạn Điều vận Giao hàng', '11-10'),
    ]

    date_from = fields.Date('Ticket Date From')
    date_to = fields.Date('Ticket Date To')
    ticket_id = fields.Many2one('ticket.helpdesk', 'Ticket')
    customer_id = fields.Many2one('res.partner', 'Customer')
    request_type = fields.Many2one('helpdesk.type', 'Request Type')
    priority_id = fields.Many2one('ticket.priority', 'Priority')
    engineer_emp = fields.Many2one('res.users', 'Engineer')
    company_id = fields.Many2one(
        'res.company', 'Branch',
        domain=lambda self: [('id', 'in', self.env.ref('base.main_company').child_ids.ids)]
    )

    line_ids = fields.One2many(
        'step.sla.compliance.wizard.line',
        'wizard_id',
        string='Lines',
        compute='_compute_lines',
        readonly=True,
        store=True,
    )

    @api.depends('date_from', 'date_to', 'ticket_id', 'customer_id',
                 'request_type', 'priority_id', 'engineer_emp', 'company_id')
    def _compute_lines(self):
        report = self.env['step.sla.compliance.report']
        for wiz in self:
            wiz.line_ids = [(5, 0, 0)]
            dom = []
            if wiz.date_from:    dom.append(('create_date', '>=', wiz.date_from))
            if wiz.date_to:      dom.append(('create_date', '<=', wiz.date_to))
            if wiz.ticket_id:    dom.append(('ticket_id', '=', wiz.ticket_id.id))
            if wiz.customer_id:  dom.append(('customer_id', '=', wiz.customer_id.id))
            if wiz.request_type: dom.append(('request_type', '=', wiz.request_type.id))
            if wiz.priority_id:  dom.append(('priority_id', '=', wiz.priority_id.id))
            if wiz.engineer_emp: dom.append(('engineer_id', '=', wiz.engineer_emp.id))
            if wiz.company_id:   dom.append(('company_id', '=', wiz.company_id.id))
            recs = report.search(dom, order='create_date desc, start_date asc')
            lines = []
            for idx, rec in enumerate(recs, start=1):
                lines.append((0, 0, {
                    'sequence': idx,
                    'ticket_id': rec.ticket_id.id,
                    'create_date': rec.create_date,
                    'customer_id': rec.customer_id.id,
                    'request_type': rec.request_type.id,
                    'priority_id': rec.priority_id.id,
                    'engineer_id': rec.engineer_id.id,
                    'step_id': rec.step_id.id,
                    'start_date': rec.start_date,
                    'end_date': rec.end_date,
                    'time_sla': rec.time_sla,
                    'time_spent': rec.time_spent,
                    'difference': rec.difference,
                    'sla_status': rec.sla_status,
                    'company_id': rec.company_id.id,
                }))
            wiz.line_ids = lines

    def _compute_display_name(self):
        for record in self:
            record.display_name = _("SLA Compliance Detail Report Wizard")

    def _write_sla_stage_rules_sheet(self, workbook):
        sheet = workbook.add_worksheet(_('SLA Stage Rules'))
        header_format = workbook.add_format({'bold': True, 'border': 1})
        cell_format = workbook.add_format({'border': 1, 'text_wrap': True})

        headers = [
            _('STT'),
            _('Tên giai đoạn'),
            _('Khoảng thời gian'),
        ]
        for column, header in enumerate(headers):
            sheet.write(0, column, header, header_format)

        sheet.set_column(0, 0, 8)
        sheet.set_column(1, 1, 36)
        sheet.set_column(2, 2, 42)

        for row_index, (sequence, name, interval) in enumerate(self.SLA_STAGE_RULES, start=1):
            sheet.write(row_index, 0, sequence, cell_format)
            sheet.write(row_index, 1, name, cell_format)
            sheet.write(row_index, 2, interval, cell_format)

    def action_export_xlsx(self):
        self.ensure_one()
        headers = [
            _('Ticket'),
            _('Customer'),
            _('Request Type'),
            _('Priority'),
            _('Engineer'),
            _('Step Name'),
            _('Step Start'),
            _('Step End'),
            _('SLA (h)'),
            _('Actual (h)'),
            _('Difference (h)'),
            _('SLA Status'),
        ]
        output = io.BytesIO()
        wb = Workbook(output, {'in_memory': True})
        sheet = wb.add_worksheet(_('SLA Compliance'))
        self._write_sla_stage_rules_sheet(wb)
        sheet.set_column(0, len(headers) - 1, 20)
        filters = [
            (_('Ticket Date From'), self.date_from.strftime('%d/%m/%Y') if self.date_from else ''),
            (_('Ticket Date To'), self.date_to.strftime('%d/%m/%Y') if self.date_to else ''),
            (_('Ticket'), self.ticket_id.name or ''),
            (_('Customer'), self.customer_id.display_name or ''),
            (_('Request Type'), self.request_type.display_name or ''),
            (_('Priority'), self.priority_id.display_name or ''),
            (_('Engineer'), self.engineer_emp.display_name or ''),
            (_('Branch'), self.company_id.display_name or ''),
        ]
        header_row, header_format = self._write_xlsx_report_header(
            wb, sheet, _('SLA Compliance Detail Report'), len(headers), filters
        )

        # write headers
        for c, h in enumerate(headers):
            sheet.write(header_row, c, h, header_format)

        # write lines
        for r, rec in enumerate(self.line_ids, start=header_row + 1):
            time_sla_label = self.float_to_time_string(rec.time_sla)
            time_spent_label = self.float_to_time_string(rec.time_spent)
            difference_label = self.float_to_time_string(rec.difference)
            start_date_label = self.convert_to_user_tz(rec.start_date).strftime(
                '%Y-%m-%d %H:%M:%S') if rec.start_date else ''
            end_date_label = self.convert_to_user_tz(rec.end_date).strftime('%Y-%m-%d %H:%M:%S') if rec.end_date else ''

            row = [
                rec.ticket_id.name or '',
                rec.customer_id.name or '',
                rec.request_type.name or '',
                rec.priority_id.name or '',
                rec.engineer_id.name or '',
                rec.step_id.name or '',
                start_date_label,
                end_date_label,
                time_sla_label,
                time_spent_label,
                difference_label,
                rec.sla_status,
            ]
            for c, v in enumerate(row):
                sheet.write(r, c, v)

        wb.close()
        data = output.getvalue()
        fname = _('SLA_Compliance_Report.xlsx')
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
