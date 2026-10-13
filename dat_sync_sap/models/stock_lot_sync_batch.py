import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)


class StockLotSyncBatch(models.Model):
    _name = 'stock.lot.sync.batch'
    _description = 'Existing Serial Number Synchronization Batch'
    _order = 'id desc'

    _ACTIVE_STATES = ('queued', 'running')
    _MAX_ERROR_LOG_LENGTH = 20000

    name = fields.Char(required=True, readonly=True)
    state = fields.Selection([
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('done_with_errors', 'Done with errors'),
        ('failed', 'Failed'),
    ], required=True, default='queued', readonly=True, index=True)
    company_id = fields.Many2one(
        'res.company', required=True, readonly=True, index=True,
        default=lambda self: self.env.company,
    )
    requested_by_id = fields.Many2one(
        'res.users', string='Requested By', required=True, readonly=True,
        default=lambda self: self.env.user,
    )
    batch_size = fields.Integer(required=True, readonly=True, default=50)
    max_lot_id = fields.Integer(required=True, readonly=True)
    last_processed_lot_id = fields.Integer(readonly=True, default=0)
    total_count = fields.Integer(readonly=True)
    processed_count = fields.Integer(readonly=True)
    success_count = fields.Integer(readonly=True)
    failure_count = fields.Integer(readonly=True)
    error_log = fields.Text(readonly=True)
    started_at = fields.Datetime(readonly=True)
    finished_at = fields.Datetime(readonly=True)

    @api.constrains('batch_size')
    def _check_batch_size(self):
        for job in self:
            if not 1 <= job.batch_size <= 500:
                raise ValidationError(_('Batch size must be between 1 and 500.'))

    @api.model
    def _lot_domain(self, company, max_lot_id=None, after_lot_id=None):
        domain = [
            ('name', '!=', False),
            ('name', '!=', ''),
            ('company_id', 'in', (False, company.id)),
        ]
        if max_lot_id is not None:
            domain.append(('id', '<=', max_lot_id))
        if after_lot_id is not None:
            domain.append(('id', '>', after_lot_id))
        return domain

    @api.model
    def queue_existing_lots(self, company, batch_size, requested_by):
        company.ensure_one()
        requested_by.ensure_one()
        batch_size = int(batch_size or 0)
        if not 1 <= batch_size <= 500:
            raise ValidationError(_('Batch size must be between 1 and 500.'))

        # Serialize job creation per company so two users cannot queue the same
        # stock lot snapshot concurrently.
        self.env.cr.execute(
            'SELECT pg_advisory_xact_lock(hashtext(%s))',
            (f'dat_sync_sap_existing_serial_queue_{company.id}',),
        )
        existing_job = self.sudo().search([
            ('company_id', '=', company.id),
            ('state', 'in', self._ACTIVE_STATES),
        ], limit=1)
        if existing_job:
            raise ValidationError(_(
                'An existing-serial synchronization is already running for '
                '%(company)s (job %(job)s).'
            ) % {
                'company': company.display_name,
                'job': existing_job.name,
            })

        lot_model = self.env['stock.lot'].sudo().with_company(company)
        domain = self._lot_domain(company)
        last_lot = lot_model.search(domain, order='id desc', limit=1)
        if not last_lot:
            raise ValidationError(_(
                'There are no existing serial numbers to synchronize for %s.'
            ) % company.display_name)

        return self.sudo().create({
            'name': _('Existing serial sync - %s') % fields.Datetime.now(),
            'company_id': company.id,
            'requested_by_id': requested_by.id,
            'batch_size': batch_size,
            'max_lot_id': last_lot.id,
            'total_count': lot_model.search_count(domain),
        })

    @api.model
    def _cron_process_pending_jobs(self):
        self = self.sudo()
        self.env.cr.execute(
            'SELECT pg_try_advisory_xact_lock(hashtext(%s))',
            ('dat_sync_sap_existing_serial_worker',),
        )
        if not self.env.cr.fetchone()[0]:
            return

        job = self.search([
            ('state', 'in', self._ACTIVE_STATES),
        ], order='id', limit=1)
        if not job:
            return

        try:
            with self.env.cr.savepoint():
                job._process_next_batch()
        except Exception as error:
            _logger.exception(
                'Existing serial batch failed | job_id=%s | company_id=%s',
                job.id,
                job.company_id.id,
            )
            job.write({
                'state': 'failed',
                'finished_at': fields.Datetime.now(),
                'error_log': job._append_error_text(
                    _('Fatal batch error: %s') % error
                ),
            })

        if job.state in self._ACTIVE_STATES:
            cron = self.env.ref(
                'dat_sync_sap.ir_cron_sync_existing_stock_lots'
            )
            cron._trigger()

    def _process_next_batch(self):
        self.ensure_one()
        if self.state not in self._ACTIVE_STATES:
            return

        if self.state == 'queued':
            self.write({
                'state': 'running',
                'started_at': fields.Datetime.now(),
            })

        lot_model = self.env['stock.lot'].sudo().with_company(self.company_id)
        lots = lot_model.search(
            self._lot_domain(
                self.company_id,
                max_lot_id=self.max_lot_id,
                after_lot_id=self.last_processed_lot_id,
            ),
            order='id',
            limit=self.batch_size,
        )
        if not lots:
            self._mark_finished()
            return

        sync_service = self.env['create.serial.wizard'].sudo().with_company(
            self.company_id
        ).create({'sync_type': 'serial'})
        success_count = 0
        failure_count = 0
        error_lines = []

        for lot in lots:
            serial_number = (lot.name or '').strip()
            error_groups = {}
            try:
                with self.env.cr.savepoint():
                    sync_service._sync_single_serial(
                        serial_number,
                        lot=lot,
                        error_groups=error_groups,
                    )
            except Exception as error:
                _logger.exception(
                    'Existing serial synchronization failed | job_id=%s | '
                    'lot_id=%s | serial=%s',
                    self.id,
                    lot.id,
                    serial_number,
                )
                error_groups.setdefault(_('Unexpected error'), []).append(str(error))

            if error_groups:
                failure_count += 1
                formatted_errors = ' | '.join(
                    part.replace('\n', ' ')
                    for part in sync_service._format_errors(error_groups)
                )
                error_lines.append(f'{serial_number}: {formatted_errors}')
            else:
                success_count += 1

        values = {
            'last_processed_lot_id': lots[-1].id,
            'processed_count': self.processed_count + len(lots),
            'success_count': self.success_count + success_count,
            'failure_count': self.failure_count + failure_count,
        }
        if error_lines:
            values['error_log'] = self._append_error_text('\n'.join(error_lines))
        self.write(values)

        _logger.info(
            'Existing serial batch processed | job_id=%s | batch=%s | '
            'processed=%s/%s | success=%s | failure=%s',
            self.id,
            len(lots),
            self.processed_count,
            self.total_count,
            self.success_count,
            self.failure_count,
        )

        if lots[-1].id >= self.max_lot_id:
            self._mark_finished()

    def _append_error_text(self, text):
        self.ensure_one()
        parts = [part for part in (self.error_log, text) if part]
        combined = '\n'.join(parts)
        if len(combined) <= self._MAX_ERROR_LOG_LENGTH:
            return combined
        suffix = _('\n... error log truncated ...')
        return combined[:self._MAX_ERROR_LOG_LENGTH - len(suffix)] + suffix

    def _mark_finished(self):
        self.ensure_one()
        self.write({
            'state': 'done_with_errors' if self.failure_count else 'done',
            'finished_at': fields.Datetime.now(),
        })
        _logger.info(
            'Existing serial synchronization finished | job_id=%s | '
            'processed=%s/%s | success=%s | failure=%s',
            self.id,
            self.processed_count,
            self.total_count,
            self.success_count,
            self.failure_count,
        )
