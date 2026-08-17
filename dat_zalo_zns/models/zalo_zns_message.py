import json
from datetime import date, datetime

import pytz
import requests
from odoo import _, api, fields, models
from odoo.addons.dat_sap_config.tools.datetime import (
    format_date_object,
    format_datetime_object,
)
from odoo.exceptions import UserError


class ZaloZnsMessage(models.Model):
    _name = 'zalo.zns.message'
    _description = 'Zalo ZNS Message'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    batch_id = fields.Many2one(
        'zalo.zns.batch', string='Batch', ondelete='set null')
    template_id = fields.Many2one(
        'zalo.zns.template',
        string='Template',
        compute='_compute_template_id',
        store=True,
        required=True,
        readonly=False)
    name = fields.Char(string='Subject')
    model_id = fields.Many2one('ir.model', string='Model')
    record_id = fields.Integer(string='Record ID')
    template_model = fields.Char(
        string='Template Model',
        related='template_id.model_id.model',
        readonly=True)
    zalo_user_id_zalo = fields.Char(string="User ID zalo")
    zalo_msg_id = fields.Char(string='Zalo Message ID', readonly=True)
    zalo_msg_str = fields.Char(string='Zalo message', readonly=True)
    phone = fields.Char(string='Phone')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('done', 'Done'),
        ('failed', 'Failed')
    ], string='State', default='draft', tracking=True)
    error_message = fields.Text(string='Error Message')
    message_type = fields.Selection(
        [('dummy', 'Dummy')], default='dummy', string='Message Type')

    @api.depends('batch_id')
    def _compute_template_id(self):
        for rec in self:
            if not rec.batch_id:
                continue
            rec.template_id = rec.batch_id.template_id

    def format_phone_number(self, phone):
        return self.env['zalo.zns.recipient'].normalize_phone(phone)

    def prepare_template_data(self):
        self.ensure_one()
        self._validate_template_record()
        template_data = {}
        template = self.template_id
        for param in template.param_ids:
            is_date_param = self._is_zns_date_param(param)
            if any([
                not template.model_id,
                not param.field_id,
                not self.model_id,
                not self.record_id,
                template.model_id.model != self.model_id.model,
            ]):
                value = param.default_value or (date.today() if is_date_param else '')
            else:
                related_record = self.env[self.model_id.model].browse(
                    self.record_id)
                value = related_record[param.field_id.name]

                # Value is a recordset
                if isinstance(value, models.BaseModel):
                    if hasattr(value, 'display_name'):
                        value = value.display_name
                    elif hasattr(value, 'name'):
                        value = value.name
                    else:
                        value = str(value)
                elif isinstance(value, datetime):
                    if is_date_param:
                        value = format_datetime_object(
                            dt_object=value,
                            tz_from=pytz.utc,
                            tz_to=pytz.timezone(
                                self.env.user.tz or 'Asia/Ho_Chi_Minh'),
                            format_to='%d/%m/%Y')
                    else:
                        value = format_datetime_object(
                            dt_object=value,
                            tz_from=pytz.utc,
                            tz_to=pytz.timezone(
                                self.env.user.tz or 'Asia/Ho_Chi_Minh'),
                            format_to='%H:%M:%S %d/%m/%Y')
                elif isinstance(value, date):
                    value = format_date_object(value, '%d/%m/%Y')
                elif value is False:
                    value = date.today() if is_date_param else ''

            if isinstance(value, date):
                value = format_date_object(value, '%d/%m/%Y')

            template_data[param.key] = value
        return template_data

    def _validate_template_record(self):
        self.ensure_one()
        template = self.template_id
        if not template.model_id:
            return

        if not self.model_id or not self.record_id:
            raise UserError(_('Please select the source record before sending this ZNS template.'))

        if template.model_id.model != self.model_id.model:
            raise UserError(
                _('Template model %(template_model)s does not match message model %(message_model)s.')
                % {
                    'template_model': template.model_id.model,
                    'message_model': self.model_id.model,
                }
            )

    def _is_zns_date_param(self, param):
        key = (param.key or '').lower()
        return (
            key.startswith('ngay')
            or 'date' in key
            or (param.field_id and param.field_id.ttype in ('date', 'datetime'))
        )

    def action_send_message_zalo_zns(self):
        config = self.env['zalo.zns.config'].get_config()
        if not config:
            return
        if (
            not config.access_token
            or (
                config.access_token_expires_at
                and config.access_token_expires_at <= fields.Datetime.now()
            )
        ):
            config.oauth(raise_exception=True)

        headers = {
            "access_token": config.access_token,
            "Content-Type": "application/json"
        }

        for message in self:
            template_data = message.prepare_template_data()
            phone = self.format_phone_number(message.phone)
            recipient = self.env['zalo.zns.recipient'].sudo().get_by_phone(
                phone,
                config.oa_id,
            )

            payload = {
                'template_id': message.template_id.template_id,
                'template_data': template_data
            }
            if recipient and recipient.zalo_user_id:
                payload['user_id'] = recipient.zalo_user_id
            else:
                payload['phone'] = phone

            try:
                response_data = message._send_template_request(config, headers, payload)

                if message._is_access_token_error(response_data):
                    config.oauth(raise_exception=True)
                    headers["access_token"] = config.access_token
                    response_data = message._send_template_request(config, headers, payload)

                if response_data.get('error') != 0 and payload.get('user_id'):
                    recipient.active = False
                    payload.pop('user_id', None)
                    payload['phone'] = phone
                    response_data = message._send_template_request(config, headers, payload)

                if response_data.get('error') == 0:
                    message.zalo_msg_str = json.dumps(response_data, ensure_ascii=False)
                    message.zalo_msg_id = (
                        self.env['zalo.zns.recipient']._extract_message_id(response_data)
                        or response_data.get('data', {}).get('msg_id')
                    )
                    recipient = self.env['zalo.zns.recipient'].sudo().upsert_from_response(
                        phone,
                        response_data,
                        config=config,
                        message=message,
                    )
                    if recipient:
                        message.zalo_user_id_zalo = recipient.zalo_user_id
                    message.state = 'sent'
                else:
                    message.state = 'failed'
                    message.error_message = response_data.get(
                        'message', 'Unknown error')

            except requests.exceptions.RequestException as e:
                message.state = 'failed'
                message.error_message = str(e)

    def _is_access_token_error(self, response_data):
        message = (
            response_data.get('message')
            or response_data.get('error_description')
            or ''
        )
        return (
            response_data.get('error') == -124
            or 'access token' in message.lower()
            or 'invalid token' in message.lower()
        )

    def _send_template_request(self, config, headers, payload):
        response = requests.post(
            f'{config.api_base_url}/message/template',
            headers=headers,
            data=json.dumps(payload),
        )
        response.raise_for_status()
        return response.json()

    def action_update_status_send_zns_from_zalo(self):
        config = self.env['zalo.zns.config'].get_config()
        if not config:
            return

        if (
            not config.access_token
            or (
                config.access_token_expires_at
                and config.access_token_expires_at <= fields.Datetime.now()
            )
        ):
            config.oauth(raise_exception=True)

        headers = {
            "access_token": config.access_token,
            "Content-Type": "application/json"
        }

        for message in self:
            zalo_api_url = f"{config.api_base_url}/message/status?message_id={message.zalo_msg_id}&phone={message.phone}"
            try:
                response = requests.get(zalo_api_url, headers=headers)
                response.raise_for_status()
                response_data = response.json()

                if response_data.get('error') == 0:
                    message.state = 'done'
                elif message._is_access_token_error(response_data):
                    config.oauth(raise_exception=True)
                    headers["access_token"] = config.access_token
                    response = requests.get(zalo_api_url, headers=headers)
                    response.raise_for_status()
                    response_data = response.json()
                    if response_data.get('error') == 0:
                        message.state = 'done'
                    else:
                        message.state = 'failed'
                        message.error_message = response_data.get(
                            'message', 'Unknown error')
                else:
                    message.state = 'failed'
                    message.error_message = response_data.get(
                        'message', 'Unknown error')

            except requests.exceptions.RequestException as e:
                message.state = 'failed'
                message.error_message = str(e)

    @api.model
    def _cron_send_messages_zalo_zns(self):
        messages = self.search([('state', '=', 'draft')])
        messages.action_send_message_zalo_zns()

    @api.model
    def _cron_update_status_send_zns_from_zalo(self):
        messages = self.search([('zalo_msg_id', '!=', '')])
        messages.action_update_status_send_zns_from_zalo()
