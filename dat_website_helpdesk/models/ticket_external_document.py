import json

from odoo import fields, models, _


class TicketExternalDocument(models.Model):
    _name = 'ticket.external.document'
    _description = 'Lịch sử chứng từ kho/ĐXVT'
    _order = 'create_date desc, id desc'

    ticket_id = fields.Many2one(
        'ticket.helpdesk', required=True, index=True, ondelete='cascade', string='Ticket'
    )
    sale_order_id = fields.Many2one(
        'sale.order', index=True, ondelete='set null', string='Báo giá'
    )
    operation = fields.Char(required=True, index=True, string='Nghiệp vụ')
    operation_name = fields.Char(required=True, string='Tên nghiệp vụ')
    document_number = fields.Char(index=True, string='Mã chứng từ')
    response_data = fields.Text(string='Phản hồi hệ thống ngoài')


class TicketExternalDocumentConfirm(models.TransientModel):
    _name = 'ticket.external.document.confirm'
    _description = 'Xác nhận tạo lại chứng từ kho/ĐXVT'

    ticket_id = fields.Many2one('ticket.helpdesk', required=True, readonly=True)
    sale_order_id = fields.Many2one('sale.order', readonly=True)
    operation = fields.Char(required=True, readonly=True)
    operation_name = fields.Char(required=True, readonly=True, string='Nghiệp vụ')
    previous_document_numbers = fields.Text(
        required=True, readonly=True, string='Các mã đã tạo trước đó'
    )
    warning_message = fields.Text(readonly=True, string='Cảnh báo')

    def action_confirm(self):
        self.ensure_one()
        context = dict(self.env.context, skip_external_document_confirmation=True)
        if self.operation.startswith('bnk:'):
            return self.ticket_id.with_context(context)._bnk_call_api(
                self.operation.split(':', 1)[1]
            )
        if self.operation == 'dxvt' and self.sale_order_id:
            return self.sale_order_id.with_context(context).action_create_sap_dxvt_single()
        return {'type': 'ir.actions.act_window_close'}


class TicketHelpdesk(models.Model):
    _inherit = 'ticket.helpdesk'

    external_document_ids = fields.One2many(
        'ticket.external.document', 'ticket_id', string='Lịch sử chứng từ ngoài'
    )
    external_document_count = fields.Integer(
        compute='_compute_external_document_count', string='Số chứng từ'
    )

    def _compute_external_document_count(self):
        grouped = self.env['ticket.external.document']._read_group(
            [('ticket_id', 'in', self.ids)], ['ticket_id'], ['__count']
        )
        counts = {ticket.id: count for ticket, count in grouped}
        for ticket in self:
            ticket.external_document_count = counts.get(ticket.id, 0)

    def _external_document_history(self, operation):
        self.ensure_one()
        return self.env['ticket.external.document'].search([
            ('ticket_id', '=', self.id),
            ('operation', '=', operation),
        ])

    def _external_document_number_from_response(self, response):
        keys = ('docnumber', 'DocNum', 'docNum', 'document_number', 'documentNumber')
        if isinstance(response, dict):
            for key in keys:
                value = response.get(key)
                if value not in (None, '', False):
                    return str(value)
            for value in response.values():
                number = self._external_document_number_from_response(value)
                if number:
                    return number
        elif isinstance(response, list):
            for value in response:
                number = self._external_document_number_from_response(value)
                if number:
                    return number
        return False

    def _record_external_document(self, operation, operation_name, document_number=False,
                                  response=False, sale_order=False):
        self.ensure_one()
        return self.env['ticket.external.document'].create({
            'ticket_id': self.id,
            'sale_order_id': sale_order.id if sale_order else False,
            'operation': operation,
            'operation_name': operation_name,
            'document_number': str(document_number) if document_number else False,
            'response_data': json.dumps(response, ensure_ascii=False, default=str) if response else False,
        })

    def _external_document_confirmation_action(self, operation, operation_name,
                                               sale_order=False):
        self.ensure_one()
        history = self._external_document_history(operation)
        if not history or self.env.context.get('skip_external_document_confirmation'):
            return False
        numbers = history.mapped('document_number')
        display_numbers = ', '.join(dict.fromkeys(filter(None, numbers))) or _('không có mã trả về')
        wizard = self.env['ticket.external.document.confirm'].create({
            'ticket_id': self.id,
            'sale_order_id': sale_order.id if sale_order else False,
            'operation': operation,
            'operation_name': operation_name,
            'previous_document_numbers': display_numbers,
            'warning_message': _(
                'Nghiệp vụ %(operation)s đã được thực hiện trước đó với mã: %(numbers)s. '
                'Bạn có muốn tiếp tục tạo thêm một chứng từ mới không?'
            ) % {'operation': operation_name, 'numbers': display_numbers},
        })
        return {
            'name': _('Xác nhận tạo lại chứng từ'),
            'type': 'ir.actions.act_window',
            'res_model': 'ticket.external.document.confirm',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_external_document_history(self):
        self.ensure_one()
        return {
            'name': _('Lịch sử chứng từ kho/ĐXVT'),
            'type': 'ir.actions.act_window',
            'res_model': 'ticket.external.document',
            'view_mode': 'tree,form',
            'domain': [('ticket_id', '=', self.id)],
            'context': {'default_ticket_id': self.id, 'create': False},
        }
