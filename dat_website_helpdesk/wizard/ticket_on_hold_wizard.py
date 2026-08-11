from odoo import _, fields, models


class TicketOnHoldWizard(models.TransientModel):
    _name = "ticket.on.hold.wizard"
    _description = "Ticket On Hold Wizard"

    ticket_id = fields.Many2one('ticket.helpdesk', string='Ticket', required=True)
    on_hold_reason = fields.Text(string='Reason for Holding', required=True)
    next_expected_survey_date = fields.Datetime(string='Next Expected Survey Date', required=True)

    def action_hold(self):
        self.ticket_id.action_hold(self.on_hold_reason, self.next_expected_survey_date)
        self.ticket_id._message_log_batch(bodies={self.ticket_id.id: _('Click On "%s"') % _('Hold')})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'sticky': False,
                'message': _('Ticket has been set on hold.'),
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
