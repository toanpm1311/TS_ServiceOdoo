from odoo import fields, models


class NotificationType(models.Model):
    _name = 'notification.type'
    _description = 'Notification Type'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, readonly=True)
