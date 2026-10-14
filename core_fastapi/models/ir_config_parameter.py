import secrets

from odoo import SUPERUSER_ID, api, models

from ..dependencies import API_KEY_PARAMETER


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    def _register_hook(self):
        result = super()._register_hook()
        self._ensure_core_api_key()
        return result

    @api.model
    def _ensure_core_api_key(self):
        parameters = self.sudo()
        # Preserve custom values, including a blank value used to disable access.
        if parameters.search([('key', '=', API_KEY_PARAMETER)], limit=1):
            return

        # Concurrent workers may initialize the same database. Insert once,
        # without overwriting the value chosen by another worker or administrator.
        self.env.cr.execute(
            """
            INSERT INTO ir_config_parameter
                (key, value, create_uid, write_uid, create_date, write_date)
            VALUES (%s, %s, %s, %s,
                    CURRENT_TIMESTAMP AT TIME ZONE 'UTC',
                    CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
            ON CONFLICT (key) DO NOTHING
            RETURNING id
            """,
            (API_KEY_PARAMETER, secrets.token_urlsafe(32), SUPERUSER_ID, SUPERUSER_ID),
        )
        if self.env.cr.fetchone():
            # Match the cache invalidation performed by the native create method.
            self.env.registry.clear_cache()
