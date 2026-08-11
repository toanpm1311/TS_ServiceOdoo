from odoo import fields, models
from datetime import timedelta

class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    def _create_date_range_seq(self, date):
        date_obj = fields.Date.from_string(date)
        year = date_obj.year
        month = date_obj.month
        date_from = fields.Date.to_string(date_obj.replace(day=1))
        if month == 12:
            next_month = date_obj.replace(year=year + 1, month=1, day=1)
        else:
            next_month = date_obj.replace(month=month + 1, day=1)
        date_to = fields.Date.to_string(next_month - timedelta(days=1))

        date_range = self.env['ir.sequence.date_range'].search([('sequence_id', '=', self.id), ('date_from', '>=', date), ('date_from', '<=', date_to)], order='date_from desc', limit=1)
        if date_range:
            date_to = date_range.date_from + timedelta(days=-1)
        date_range = self.env['ir.sequence.date_range'].search([('sequence_id', '=', self.id), ('date_to', '>=', date_from), ('date_to', '<=', date)], order='date_to desc', limit=1)
        if date_range:
            date_from = date_range.date_to + timedelta(days=1)
        seq_date_range = self.env['ir.sequence.date_range'].sudo().create({
            'date_from': date_from,
            'date_to': date_to,
            'sequence_id': self.id,
        })
        return seq_date_range