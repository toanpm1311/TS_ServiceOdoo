from odoo import fields, models, api, _


class TicketStep(models.Model):
    _inherit = 'ticket.step'

    step_sla_hours = fields.Float(string='SLA Hours', default=4.0)
    notify_zalo = fields.Boolean(string="Send Zalo notification")
    template_zalo = fields.Many2one('zalo.zns.template', string='Zalo Template',
                                    ondelete='cascade')

    # Assignee email notification fields
    notify_assignee_email_on_enter = fields.Boolean(string="Notify Assignee on Step Enter")
    email_template_assignee_enter = fields.Many2one(
        'mail.template',
        string="Assignee Email Template (on enter)",
        domain="[('model', '=', 'ticket.helpdesk')]",
        default=lambda self: self.env.ref('dat_helpdesk_steps_sla.ticket_notify_assignee_on_enter',
                                          raise_if_not_found=False)
    )

    notify_assignee_email_before_deadline = fields.Boolean(string="Notify Assignee before Deadline")
    notify_before_minutes = fields.Integer(
        string="Minutes before Deadline",
        default=60,
        help="Send email this many minutes before the deadline"
    )
    email_template_assignee_deadline = fields.Many2one(
        'mail.template',
        string="Assignee Email Template (before deadline)",
        domain="[('model', '=', 'ticket.helpdesk')]",
        default=lambda self: self.env.ref('dat_helpdesk_steps_sla.ticket_notify_assignee_before_deadline',
                                          raise_if_not_found=False)
    )

    # Leader email notification fields
    notify_leader_email_on_enter = fields.Boolean(string="Notify Leader on Step Enter")
    email_template_leader_enter = fields.Many2one(
        'mail.template',
        string="Leader Email Template (on enter)",
        domain="[('model', '=', 'ticket.helpdesk')]",
        default=lambda self: self.env.ref('dat_helpdesk_steps_sla.ticket_notify_leader_on_step',
                                          raise_if_not_found=False)
    )

    notify_leader_email_before_deadline = fields.Boolean(string="Notify Leader before Deadline")
    email_template_leader_deadline = fields.Many2one(
        'mail.template',
        string="Leader Email Template (before deadline)",
        domain="[('model', '=', 'ticket.helpdesk')]",
        default=lambda self: self.env.ref('dat_helpdesk_steps_sla.ticket_notify_leader_on_step',
                                          raise_if_not_found=False)
    )

    @api.onchange('notify_assignee_email_on_enter')
    def _onchange_notify_assignee_email_on_enter(self):
        if not self.notify_assignee_email_on_enter:
            self.notify_leader_email_on_enter = False

    @api.onchange('notify_assignee_email_before_deadline')
    def _onchange_notify_assignee_email_before_deadline(self):
        if not self.notify_assignee_email_before_deadline:
            self.notify_leader_email_before_deadline = False
