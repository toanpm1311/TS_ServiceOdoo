import time

import requests
from odoo import _, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # SAP connection info
    sap_api_url = fields.Char(
        config_parameter='dat_sync_sap.sap_api_url')
    sap_auth_url = fields.Char(
        config_parameter='dat_sync_sap.sap_auth_url')
    sap_auth_username = fields.Char(
        config_parameter='dat_sync_sap.sap_auth_username')
    sap_auth_password = fields.Char(
        config_parameter='dat_sync_sap.sap_auth_password')

    # In-memory token storage (will reset on Odoo restart)
    _sap_token_cache = {
        'token': None,
        'expires_at': 0
    }

    def auth_sap(self):
        param_model = self.env['ir.config_parameter'].sudo()
        sap_auth_url = param_model.get_param(
            'dat_sync_sap.sap_auth_url')
        sap_auth_username = param_model.get_param(
            'dat_sync_sap.sap_auth_username')
        sap_auth_password = param_model.get_param(
            'dat_sync_sap.sap_auth_password')

        if all([sap_auth_url, sap_auth_username, sap_auth_password]):
            headers = {
                'Content-Type': 'application/json',
            }
            return requests.post(sap_auth_url, headers=headers, json={
                "username": sap_auth_username,
                "password": sap_auth_password,
            })
        raise UserError(
            _('Please provide complete information for the SAP connection in the DAT Settings.'))

    def _get_sap_token(self):
        now = time.time()
        if self._sap_token_cache['token'] and self._sap_token_cache['expires_at'] > now:
            return self._sap_token_cache['token']

        # Fetch new token from SAP API
        response = self.auth_sap()

        if response.status_code == 200:
            result = response.json()
            token = result.get('token')
            expires_in = 3600  # default 1h
            try:
                time_live = result.get('timeLive', '1 Hours')
                if time_live:
                    time_live_info = time_live.split(' ')
                    time_live = int(time_live_info[0])
                    time_unit = time_live_info[1]
                    if time_unit.lower() == 'hours':
                        expires_in = time_live * 3600
            except Exception:
                pass

            self._sap_token_cache['token'] = token
            self._sap_token_cache['expires_at'] = now + \
                expires_in - 60  # buffer 1 min
            return token
        else:
            raise UserError(_("Failed to get SAP token: %s") % response.reason)

    def get_sap_headers(self):
        token = self._get_sap_token()
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
        }

    def action_test_sap_connection(self):
        res = self.auth_sap()
        if res and res.status_code == 200:
            noti_type = 'success'
            noti_message = _("Connect successfully.")
        else:
            noti_type = 'danger'
            noti_message = _("Connect failed!")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                    'type': noti_type,
                    'sticky': False,
                    'message': noti_message,
            }
        }
