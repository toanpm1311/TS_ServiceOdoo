from odoo import models, fields, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    mail_firebase_tokens = fields.One2many("mail.firebase", "partner_id")
