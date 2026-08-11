from odoo import _, fields, models


class TicketRejectWizard(models.TransientModel):
    _name = "ticket.reject.wizard"
    _description = "Ticket Reject Wizard"

    ticket_id = fields.Many2one('ticket.helpdesk', string='Ticket', required=True)
    reject_reason = fields.Text(string='Reason for Rejection', required=True)

    def action_reject(self):
        self.ticket_id.action_reject(self.reject_reason)
        self.ticket_id._message_log_batch(bodies={self.ticket_id.id: _('Click On "%s"') % _('Reject')})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'sticky': False,
                'message': _('Ticket has been rejected.'),
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
