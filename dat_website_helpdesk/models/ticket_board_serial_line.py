from odoo import fields, models


class TicketBoardSerialLine(models.Model):
    _name = 'ticket.board.serial.line'
    _description = 'Ticket Board Serial Line'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    ticket_id = fields.Many2one(
        'ticket.helpdesk',
        string='Ticket',
        required=True,
        ondelete='cascade',
    )
    old_board_serial = fields.Char(string='Số seri bo cũ')
    new_board_serial = fields.Char(string='Số seri bo mới')
    board_serial_date = fields.Date(string='Ngày')
