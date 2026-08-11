from odoo import models, fields, _


class ResUsers(models.Model):
    _inherit = "res.users"

    mail_firebase_tokens = fields.One2many("mail.firebase", "user_id")
