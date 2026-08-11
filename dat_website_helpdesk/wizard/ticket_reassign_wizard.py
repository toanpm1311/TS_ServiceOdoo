from odoo import _, fields, models, api
from odoo.exceptions import UserError


class TicketReassignWizard(models.TransientModel):
    _name = "ticket.reassign.wizard"
    _description = "Ticket Reassign Wizard"

    ticket_id = fields.Many2one('ticket.helpdesk', string='Ticket', required=True)
    allowed_user_ids = fields.Many2many(
        'res.users',
        string='Allowed Users',
        readonly=True,
    )
    new_user_id = fields.Many2one(
        'res.users',
        string='New Assignee',
        required=True,
    )
    is_reassign = fields.Boolean('Is Reassign', default=False, help="Indicates if the ticket is being reassigned.")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ticket_id = self.env.context.get('default_ticket_id')
        res.setdefault('ticket_id', ticket_id)

        ticket = self.env['ticket.helpdesk'].browse(ticket_id)

        assigned_user = ticket.assigned_user_id
        helpdesk_group = self.env.ref('dat_website_helpdesk.helpdesk_user')

        company_ids = assigned_user.company_ids.ids
        emps = self.env['hr.employee'].search([
            ('company_id', 'in', company_ids)
        ])

        user_ids = emps.mapped('user_id').filtered(
            lambda u: helpdesk_group in u.groups_id
        )
        res['allowed_user_ids'] = [(6, 0, user_ids.ids)]

        return res


    def action_confirm(self):
        self.ensure_one()
        ticket = self.ticket_id
        is_reassign = self.env.context.get('is_reassign')

        if is_reassign:
            if self.new_user_id == ticket.assigned_user_id:
                raise UserError(_("The selected user is already assigned."))
            self.ticket_id.action_reassign(self.new_user_id)
            self.ticket_id._message_log_batch(
                bodies={
                    self.ticket_id.id: _('Click On "%s".\nNew assignee: %s') % (_('Reassign'), self.new_user_id.display_name)})
        else:
            self.ticket_id.action_assigned(self.new_user_id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'sticky': False,
                'message': _('Ticket has been reassigned.'),
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
