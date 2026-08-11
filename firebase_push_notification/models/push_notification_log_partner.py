from odoo import models, fields, _


class PushNotificationLogPartner(models.Model):
    _name = 'push.notification.log.partner'
    _order = 'id desc'

    notification_id = fields.Many2one('mobile.app.push.notification', 'Notification')
    partner_id = fields.Many2one('res.partner', 'Partner')
    name = fields.Char(string='Title', related='notification_id.name', readonly=True)
    body = fields.Text(string='Message', readonly=True,related='notification_id.body', )
    date_send = fields.Datetime("Send Date")
    device_token = fields.Char('Token')
    notification_state = fields.Selection([('success', 'Success'), ('failed', 'Failed')], 'Notification State',)
    state = fields.Selection([('viewed', 'Viewed'), ('not_viewed', 'Not Viewed'),
                             ('failed', 'Failed')], 'State', default='not_viewed')
