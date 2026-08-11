from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    api_debug = fields.Boolean(
        config_parameter='core_fastapi.api_debug')
