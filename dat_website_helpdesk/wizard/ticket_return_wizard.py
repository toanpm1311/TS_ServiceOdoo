from odoo import _, fields, models


class TicketReturnWizard(models.TransientModel):
    _name = "ticket.return.wizard"
    _description = "Ticket Return Wizard"

    ticket_id = fields.Many2one('ticket.helpdesk', string='Ticket', required=True)
    return_reason = fields.Text(string='Reason for Return', required=True)

    def action_return(self):
        self.ticket_id.action_return_step()
        self.ticket_id._message_log_batch(bodies={self.ticket_id.id: _('Click On "%s".\nReturn Step Reason: %s') % (_('Return'), self.return_reason)})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'sticky': False,
                'message': _('Ticket has been returned.'),
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
