import logging
from urllib.parse import urlparse

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class N8nNotification(models.Model):
    _name = 'ts.n8n.notification'
    _description = 'TechService n8n notification delivery'
    _order = 'id desc'

    event_key = fields.Char(required=True, readonly=True, index=True)
    event_type = fields.Selection([
        ('quotation_sent', 'Gửi báo giá'), ('quotation_reminder', 'Nhắc báo giá'),
        ('ticket_alert', 'Cảnh báo ticket'),
    ], required=True, readonly=True)
    channel = fields.Selection([('email', 'Email'), ('teams', 'Teams riêng')], required=True, readonly=True)
    recipient = fields.Char(required=True, readonly=True)
    title = fields.Char(required=True, readonly=True)
    body = fields.Text(required=True, readonly=True)
    ticket_id = fields.Many2one('ticket.helpdesk', readonly=True, ondelete='cascade')
    order_id = fields.Many2one('sale.order', readonly=True, ondelete='cascade')
    attachment_id = fields.Many2one('ir.attachment', readonly=True, ondelete='set null')
    company_id = fields.Many2one('res.company', required=True, readonly=True)
    state = fields.Selection([
        ('pending', 'Chờ gửi'), ('sent', 'Đã gửi'), ('failed', 'Lỗi gửi'), ('cancelled', 'Đã hủy'),
    ], default='pending', required=True, readonly=True, index=True)
    sent_at = fields.Datetime(readonly=True)
    last_error = fields.Text(string='Lỗi', readonly=True)

    _sql_constraints = [
        ('event_channel_unique', 'unique(event_key, channel)', 'Thông báo đã tồn tại cho kênh này.'),
    ]

    @api.model
    def _enqueue(self, event_key, event_type, recipient, title, body, ticket, order=None, attachment=None):
        for channel in ('email', 'teams'):
            if not self.search_count([('event_key', '=', event_key), ('channel', '=', channel)]):
                self.create({
                    'event_key': event_key, 'event_type': event_type, 'channel': channel,
                    'recipient': recipient, 'title': title, 'body': body,
                    'ticket_id': ticket.id, 'order_id': order.id if order else False,
                    'attachment_id': attachment.id if attachment else False,
                    'company_id': (order.company_id if order else ticket.branch or self.env.company).id,
                })

    def action_retry(self):
        # A network timeout can occur after Microsoft accepted the message.
        # An operator must inspect n8n execution before explicitly retrying.
        self.filtered(lambda message: message.state == 'failed').write({'state': 'pending', 'last_error': False})
        return True

    def _ts_payload(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        record = self.order_id or self.ticket_id
        payload = {
            'event_id': '%s:%s' % (self.event_key, self.channel), 'channel': self.channel,
            'event_type': self.event_type, 'recipient': self.recipient,
            'subject': self.title, 'body': self.body,
            'record_url': '%s/web#id=%s&model=%s&view_type=form' % (base_url, record.id, record._name),
            'ticket_id': self.ticket_id.id, 'quotation_id': self.order_id.id or None,
        }
        if self.channel == 'email' and self.attachment_id:
            data = self.attachment_id.datas
            payload['attachment'] = {
                'name': self.attachment_id.name, 'content_type': 'application/pdf',
                'content_base64': data.decode() if isinstance(data, bytes) else data,
            }
        return payload

    def _ts_mark_sent(self):
        self.ensure_one()
        now = fields.Datetime.now()
        self.write({'state': 'sent', 'sent_at': now, 'last_error': False})
        order = self.order_id
        if order and self.event_type == 'quotation_sent' and not order.ts_quotation_sent_at:
            siblings = self.search([('event_key', '=', self.event_key)])
            if len(siblings) == 2 and all(message.state == 'sent' for message in siblings):
                order.write({'ts_quotation_sent_at': now, 'ts_response_due_at': order._ts_due_at(now)})
                order.message_post(body=_('n8n xác nhận đã gửi email và Teams cho sale.'))

    def _ts_dispatch_one(self, url, token):
        self.ensure_one()
        order = self.order_id
        if order and (order.state == 'cancel' or order.status in ('cancelled', 'rejected')):
            self.state = 'cancelled'
            return
        if self.event_type == 'quotation_reminder' and (not order or not order._ts_waiting_response()):
            self.state = 'cancelled'
            return
        try:
            payload = self._ts_payload()
            response = requests.post(
                url, json=payload, headers={'X-TechService-Token': token},
                timeout=(5, 30), allow_redirects=False,
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict) or result.get('delivered') is not True or result.get('event_id') != payload['event_id']:
                raise ValueError('n8n did not acknowledge this event as delivered')
            self._ts_mark_sent()
        except (requests.RequestException, ValueError, UserError) as error:
            # Avoid leaking token/URL/response bodies to chatter.
            self.write({'state': 'failed', 'last_error': type(error).__name__})
            if self.ticket_id:
                self.ticket_id.message_post(body=_('Thông báo %(channel)s gửi qua n8n thất bại. Quản trị viên kiểm tra Hàng đợi thông báo và execution n8n trước khi gửi lại.') % {'channel': self.channel})

    @api.model
    def _cron_dispatch(self):
        params = self.env['ir.config_parameter'].sudo()
        url = params.get_param('ts_techservice_n8n.webhook_url', '')
        token = params.get_param('ts_techservice_n8n.webhook_token', '')
        if not url or not token:
            return
        if urlparse(url).scheme != 'https':
            _logger.error('TechService n8n webhook must use HTTPS')
            return
        # Bound the work and lock rows to avoid competing dispatchers.
        self.env.cr.execute("SELECT id FROM ts_n8n_notification WHERE state = 'pending' ORDER BY id LIMIT 2 FOR UPDATE SKIP LOCKED")
        messages = self.browse([row[0] for row in self.env.cr.fetchall()])
        for message in messages:
            message._ts_dispatch_one(url, token)
