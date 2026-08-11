# -*- coding: utf-8 -*-
from odoo import models, fields

class PushNotificationLogPartner(models.Model):
    _name = "push.notification.log.partner"
    _description = "Push Notification Log - Partner"

    partner_id = fields.Many2one("res.partner", required=True)
    message = fields.Char()
    status = fields.Selection(
        [("sent", "Sent"), ("fail", "Failed")],
        default="sent"
    )
    sent_at = fields.Datetime(default=fields.Datetime.now)
