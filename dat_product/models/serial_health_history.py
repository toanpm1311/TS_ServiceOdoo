from odoo import models, fields


class SerialHealthHistory(models.Model):
    _name = 'serial.health.history'
    _description = 'Serial Health History'
    _order = 'checking_date, lot_id'

    status_before_repair = fields.Char(string='Status Before Repair')
    status_after_repair = fields.Char(string='Status After Repair')
    checking_date = fields.Datetime(string='Checking Date', default=fields.Datetime.now)
    recorded_by = fields.Many2one(
        'res.users', string='Recorded By', default=lambda self: self.env.user, required=True)
    lot_id = fields.Many2one('stock.lot', string='Serial Number', required=True)
