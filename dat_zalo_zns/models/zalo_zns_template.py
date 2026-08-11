from odoo import _, fields, models


class ZaloZnsTemplate(models.Model):
    _name = 'zalo.zns.template'
    _description = 'Zalo ZNS Template'

    name = fields.Char(string='Template Name', required=True)
    template_id = fields.Char(string='Template ID', required=True)
    description = fields.Text(string='Description')
    preview_url = fields.Char(string='Preview URL')
    param_ids = fields.One2many('zalo.zns.template.param', 'template_id')
    model_id = fields.Many2one('ir.model', string='Model')

    def action_send_message(self):
        return {
            'name': _('Send Zalo ZNS Message'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'zalo.zns.send.message.wizard',
            'target': 'new',
            'context': {'default_template_id': self.id},
        }
