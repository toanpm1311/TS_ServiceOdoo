from odoo import api, fields, models, _
from odoo.addons.dat_website_helpdesk.fields.custom_float import CustomFloat
from odoo.exceptions import ValidationError


class TaskAllocation(models.Model):
    _name = 'task.allocation'
    _description = 'Task Allocation'

    sequence = fields.Integer(string='Sequence', default=1)
    ticket_id = fields.Many2one('ticket.helpdesk', string='Ticket')
    user_id = fields.Many2one('res.users', string='Assigned User', required=True)
    weight = CustomFloat(string='Weight (%)', digits=(16, 4))
    note = fields.Text(string='Note')
    point = fields.Float(string='Point',
                         compute='_compute_point',
                         store=True)

    _sql_constraints = [('ticket_user_uniq', 'unique (ticket_id,user_id)',
                         'The User cannot be duplicated!')]

    @api.constrains('weight')
    def _check_weight_range(self):
        for rec in self:
            if rec.weight < 0 or rec.weight > 1:
                raise ValidationError(_("Trọng số phải nằm trong khoảng từ 0 đến 100."))

    @api.depends('weight', 'ticket_id.solution_total_point_with_complexity')
    def _compute_point(self):
        for rec in self:
            total = rec.ticket_id.solution_total_point_with_complexity or 0.0
            w = rec.weight or 0.0
            rec.point = total * w
