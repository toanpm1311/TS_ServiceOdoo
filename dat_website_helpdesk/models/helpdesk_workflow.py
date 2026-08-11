from odoo import fields, models


class HelpdeskWorkflow(models.Model):
    _name = 'helpdesk.workflow'
    _description = 'Helpdesk Workflow'

    name = fields.Char('Name', required=True, translate=True)
    active = fields.Boolean('Active', default=True)
    step_ids = fields.One2many('ticket.step', 'workflow_id',
                               string='Steps')
    helpdesk_ids = fields.One2many('ticket.helpdesk', 'workflow_id',
                                   string='Helpdesk Tickets')
    helpdesk_count = fields.Integer('Helpdesk Count', compute='_compute_helpdesk_count')
    code = fields.Char('Code', compute='_compute_code', store=True)

    def _compute_helpdesk_count(self):
        for rec in self:
            rec.helpdesk_count = len(rec.helpdesk_ids)

    def _compute_code(self):
        res = self.get_external_id()
        for rec in self:
            rec.code = res.get(rec.id).split('.')[-1]
