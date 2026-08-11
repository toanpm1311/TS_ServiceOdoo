from datetime import datetime

from dateutil.relativedelta import relativedelta
from odoo import fields, models


class IrCronTrigger(models.Model):
    _name = 'ir.cron.history'
    _order = 'id desc'

    cron_id = fields.Many2one("ir.cron", readonly=True)
    create_date = fields.Datetime(readonly=True)
    status = fields.Selection(
        selection=[
            ('failed', 'Failed'),
            ('done', 'Done'),
        ], default='done')
    error_message = fields.Text(string='Error Message', readonly=True)

    def clean_cron_histories(self):
        records_removed = self.search([
            ('create_date', '<', datetime.now() + relativedelta(weeks=-1)),
        ])
        return records_removed.unlink()
