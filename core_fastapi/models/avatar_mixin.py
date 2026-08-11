from odoo import api, fields, models


class AvatarMixin(models.AbstractModel):
    _inherit = 'avatar.mixin'

    avatar_256_url = fields.Char(
        string='Avatar 256 URL', compute='_compute_avatar_256_url')

    @api.depends('avatar_256')
    def _compute_avatar_256_url(self):
        base_url = self.env['ir.config_parameter'].sudo(
        ).get_param('web.base.url')
        for rec in self:
            rec.avatar_256_url = '%s/web/image?model=%s&id=%s&field=avatar_256' % (
                base_url, self._name, rec.id)
