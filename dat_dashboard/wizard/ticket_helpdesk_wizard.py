# -*- coding: utf-8 -*-
import io
import base64
from odoo import api, fields, models, _
from xlsxwriter import Workbook
from ..models.common_utils_mixin import CommonUtilsMixin
import logging

_logger = logging.getLogger(__name__)

class TicketWizardLine(models.TransientModel):
    _name = 'ticket.wizard.line'
    _description = 'Line for Ticket Wizard'

    wizard_id = fields.Many2one('ticket.wizard', string='Wizard')
    stt = fields.Integer(string='STT')
    customer_contact_name = fields.Char(string='Tên khách hàng')
    subject = fields.Char(string='Tiêu đề')
    description = fields.Text(string='Mô tả')
    status = fields.Char(string='Trạng thái')


class TicketWizard(models.TransientModel, CommonUtilsMixin):
    _name = 'ticket.wizard'
    _description = 'Total Time Ticket & Research Steps Report Wizard'

    customer_name = fields.Many2one('ticket.helpdesk', string='Customer Name')
    line_ids = fields.One2many(
        'ticket.wizard.line',
        'wizard_id',
        string='Ticket Lines',
        compute='_compute_line_ids',
        store=True,
        readonly=True,
    )

    @api.depends('customer_name')
    def _compute_line_ids(self):
        self.ensure_one()
        self.line_ids = [(5, 0, 0)] + self._get_filtered_ticket_lines()

    def action_load_lines(self):
        _logger.info('Load Tickets clicked')
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def _get_filtered_ticket_lines(self):
        domain = []
        if self.customer_name:
            domain.append(('id', '=', self.customer_name.id))
     
        tickets = self.env['ticket.helpdesk'].search(domain)

        lines = []
        for idx, ticket in enumerate(tickets, start=1):
            lines.append((0, 0, {
                'stt': idx,
                'customer_contact_name': ticket.customer_contact_name,
                'subject': ticket.subject,
                'description': ticket.description,
                'status': ticket.status,
            }))
        return lines

    def action_export_xlsx(self):
        self.ensure_one()  # chỉ xử lý một wizard tại một thời điểm

        domain = []
        if self.customer_name:
            domain.append(('customer_contact_name', '=', self.customer_name))
        

        tickets = self.env['ticket.helpdesk'].search(domain)

        output = io.BytesIO()
        workbook = Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('KPI')
    
        headers = ['STT', 'Tên khách hàng', 'Tiêu đề', 'Mô tả', 'Trạng thái']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header)

        for row_num, ticket in enumerate(tickets, start=1):
            worksheet.write(row_num, 0, row_num)
            worksheet.write(row_num, 1, ticket.customer_contact_name or '')
            worksheet.write(row_num, 2, ticket.subject or '')
            worksheet.write(row_num, 3, ticket.description or '')
            worksheet.write(row_num, 4, ticket.status or '')

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()

        filename = 'ticket_report.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': file_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    

