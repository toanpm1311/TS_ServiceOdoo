from odoo import models, fields


class PushNotificationLogHistory(models.Model):
    _name = 'push.notification.log.history'
    _description = 'History of push notification'

    notification_id = fields.Many2one('mobile.app.push.notification')
    date_send = fields.Datetime("Send Date")
    notification_state = fields.Selection(
        [('success', 'Success'), ('failed', 'Failed')], string="State")
