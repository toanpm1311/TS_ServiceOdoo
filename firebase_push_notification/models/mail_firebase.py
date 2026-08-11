from odoo import models, fields, _


class MailFirebase(models.Model):
    _name = "mail.firebase"
    _description = 'Firebase Device Token'

    user_id = fields.Many2one('res.users', string="User", readonly=False)
    partner_id = fields.Many2one('res.partner', string="Partner", readonly=False)
    os = fields.Char(string="Device OS", readonly=False)
    token = fields.Char(string="Device firebase token", readonly=False)

    _sql_constraints = [
        ('token', 'unique(token, os, user_id)', 'Token must be unique per user!'),
        ('token_not_false', 'CHECK (token IS NOT NULL)', 'Token must be not null!'),
    ]
