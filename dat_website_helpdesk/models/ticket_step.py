from odoo import fields, models, _
from odoo.exceptions import UserError


class TicketStep(models.Model):
    _name = 'ticket.step'
    _description = 'Ticket Step'
    _order = 'sequence, id'
    _fold_name = 'fold'

    name = fields.Char('Name', translate=True)
    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer(string='Sequence', default=50)
    closing_step = fields.Boolean('Closing Step', default=False)
    template_id = fields.Many2one('mail.template', string='Template',
                                  domain="[('model', '=', 'ticket.helpdesk')]")
    group_ids = fields.Many2many('res.groups', string='Groups')

    workflow_id = fields.Many2one('helpdesk.workflow', string='Workflow', ondelete='cascade')
    code = fields.Char('Code', compute='_compute_code', store=True)

    def _compute_code(self):
        res = self.get_external_id()
        for rec in self:
            rec.code = res.get(rec.id).split('.')[-1]
