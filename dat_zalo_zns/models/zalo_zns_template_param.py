from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ZaloZnsTemplateParam(models.Model):
    _name = 'zalo.zns.template.param'
    _description = 'Zalo ZNS Template Param'

    template_id = fields.Many2one(
        'zalo.zns.template', string='Template', required=True, ondelete='cascade')
    key = fields.Char(string='Key', required=True)
    default_value = fields.Char()
    field_id = fields.Many2one('ir.model.fields', string='Field')

    @api.onchange('template_id.model_id')
    def _onchange_model_id(self):
        self.field_id = False
