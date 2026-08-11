import logging
from datetime import timedelta

import requests
from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ZALO_ZNS_API_BASE_URL = 'https://business.openapi.zalo.me'
ZALO_OAUTH_API_URL = 'https://oauth.zaloapp.com/v4/oa/access_token'
ZALO_DAT_APP_ID = '4518017362122335698'
ZALO_DAT_OA_ID = '1341571649425662683'
ZALO_DAT_OA_NAME = 'DAT Technology'


class ZaloZnsConfig(models.Model):
    _name = 'zalo.zns.config'
    _description = 'Zalo ZNS Configuration'
    _order = 'sequence, id'

    name = fields.Char(string='Configuration Name',
                       required=True, default='DAT Technology ZNS')
    api_base_url = fields.Char(
        string='API Base URL',
        required=True,
        default=ZALO_ZNS_API_BASE_URL)
    access_token = fields.Char(string='Access Token')
    access_token_expires_at = fields.Datetime(
        string='Access Token Expiration At')
    sequence = fields.Char(default=0)
    active = fields.Boolean(default=True)

    # refresh token
    oauth_api_url = fields.Char(
        string='OAuth API URL',
        required=True,
        default=ZALO_OAUTH_API_URL,
        help="URL to use for refreshing the access token.")
    refresh_token = fields.Char(
        string='Refresh Token',
        required=True,
        help="Refresh Token to use for refreshing the access token.")
    app_id = fields.Char(
        string='App ID',
        required=True,
        default=ZALO_DAT_APP_ID,
        help="App ID to use for refreshing the access token.")
    oa_id = fields.Char(
        string='Official Account ID',
        default=ZALO_DAT_OA_ID,
        help="Zalo Official Account connected to this ZNS app.")
    oa_name = fields.Char(
        string='Official Account Name',
        default=ZALO_DAT_OA_NAME)

    @api.model
    def _get_secret_key(self):
        secret_key = tools.config.get('zalo_secret_key')
        if not secret_key:
            raise UserError(_('Please add the zalo_secret_key in the Odoo config file.'))
        return secret_key

    @api.model
    def get_config(self):
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            raise UserError(_('You have to add Zalo ZNS Configuration first.'))
        return config

    def oauth(self, raise_exception=False):
        self.ensure_one()
        secret_key = self._get_secret_key()
        headers = {
            'secret_key': secret_key,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        payload = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'app_id': self.app_id,
            'secret_key': secret_key,
        }
        try:
            _logger.info(
                "Refreshing Zalo ZNS access token for config %s with app_id %s",
                self.display_name,
                self.app_id,
            )
            response = requests.post(
                self.oauth_api_url,
                headers=headers,
                data=payload)
            response.raise_for_status()
            response_data = response.json()

            if 'error' not in response_data:
                expires_in = int(response_data['expires_in']) - 60  # buffer 1 min
                self.write({
                    'access_token': response_data['access_token'],
                    'access_token_expires_at': fields.Datetime.now() + timedelta(seconds=expires_in),
                    'refresh_token': response_data.get('refresh_token') or self.refresh_token,
                })
                return True
            else:
                error_message = response_data.get(
                    'error_description') or response_data.get('message') or str(response_data)
                _logger.warning(error_message)
                if raise_exception:
                    raise UserError(_('Cannot refresh Zalo access token: %s') % error_message)

        except requests.exceptions.RequestException as e:
            _logger.warning(str(e))
            if raise_exception:
                raise UserError(_('Cannot refresh Zalo access token: %s') % str(e))
        return False

    @api.model
    def _cron_refresh_zalo_access_tokens(self):
        for config in self.search([('active', '=', True)]):
            config.oauth()
