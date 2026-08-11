import logging
from datetime import datetime

import pytz
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class IrCron(models.Model):
    _inherit = 'ir.cron'

    lastcall_success = fields.Datetime(
        string='Last Execution Success', help="Previous time the cron ran successfully, not raise error.")
    save_log = fields.Boolean(
        string='Save Log',
        help="If checked, the cron will save its execution log.",
        default=False)

    _cron_cache = {
        'error': False
    }

    @api.model
    def _handle_callback_exception(self, cron_name, server_action_id, job_id, job_exception):
        super()._handle_callback_exception(
            cron_name, server_action_id, job_id, job_exception)
        cron = self.browse(job_id).exists()
        if cron.save_log:
            self.env['ir.cron.history'].create({
                'cron_id': job_id,
                'status': 'failed',
                'error_message': str(job_exception),
            })
        self._cron_cache['error'] = True

    @classmethod
    def _process_job(cls, db, cron_cr, job):
        cls._cron_cache['error'] = False
        super()._process_job(db, cron_cr, job)
        if not cls._cron_cache['error']:
            cron_cr.execute("""
                UPDATE ir_cron
                SET lastcall_success=%s
                WHERE id=%s
            """, [
                fields.Datetime.to_string(datetime.now(pytz.utc)),
                job['id'],
            ])
