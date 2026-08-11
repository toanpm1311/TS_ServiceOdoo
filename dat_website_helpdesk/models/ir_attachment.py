from odoo import api, fields, models, SUPERUSER_ID, tools, _


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    public = fields.Boolean('Is public document', default=True)