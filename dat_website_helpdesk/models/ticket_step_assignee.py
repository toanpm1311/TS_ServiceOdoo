from odoo import api, fields, models, _

class TicketStepAssignee(models.Model):
    _name = 'ticket.step.assignee'
    _description = 'Ticket Step Assignee'

    ticket_id = fields.Many2one('ticket.helpdesk', string='Ticket')
    step_id = fields.Many2one('ticket.step', string='Step')
    user_id = fields.Many2one('res.users', string='Assigned User', required=True)
    done = fields.Boolean(string='Done', default=False)