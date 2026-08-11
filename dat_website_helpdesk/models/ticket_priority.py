from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class TicketPriority(models.Model):
    _name = 'ticket.priority'
    _description = 'Ticket Priority'

    name = fields.Char(string='Priority', translate=True)
    code = fields.Char(string='Code')
    percentage_hours = fields.Float(string='Percentage Hours (%)')
    default = fields.Boolean(string='Default')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'The code must be unique!'),
    ]

    @api.constrains('default')
    def _check_default(self):
        for rec in self:
            if rec.default and self.search_count([('default', '=', True)]) != 1:
                    raise ValidationError(_(
                        "You must have one default priority."
                    ))

    def unlink(self):
        for rec in self:
            if rec.default:
                raise ValidationError(_(
                    "You cannot delete the default priority."
                ))
        return super().unlink()

    def choose_default(self):
        if len(self) > 1:
                raise ValidationError(_(
                    "You can only choose one default priority."
                ))
        self.search([('default', '=', True)]).write({'default': False})
        self.write({'default': True})
