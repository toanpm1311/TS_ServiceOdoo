import re

from odoo import api, fields, models


class ZaloZnsRecipient(models.Model):
    _name = 'zalo.zns.recipient'
    _description = 'Zalo ZNS Recipient UID Mapping'
    _rec_name = 'phone'

    phone = fields.Char(required=True, index=True)
    zalo_user_id = fields.Char(string='Zalo UID', required=True, index=True)
    oa_id = fields.Char(string='OA ID', index=True)
    last_message_id = fields.Char(string='Last Zalo Message ID')
    last_sent_at = fields.Datetime(string='Last Sent At')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'phone_oa_unique',
            'unique(phone, oa_id)',
            'Each phone can only have one Zalo UID per OA.',
        ),
    ]

    @api.model
    def normalize_phone(self, phone):
        phone = re.sub(r'\D', '', phone or '')
        if phone.startswith('0'):
            phone = '84' + phone[1:]
        if phone and not phone.startswith('84'):
            phone = '84' + phone
        return phone

    @api.model
    def get_by_phone(self, phone, oa_id=False):
        normalized_phone = self.normalize_phone(phone)
        if not normalized_phone:
            return self.browse()
        domain = [
            ('phone', '=', normalized_phone),
            ('active', '=', True),
        ]
        if oa_id:
            domain.append(('oa_id', '=', oa_id))
        return self.search(domain, limit=1)

    @api.model
    def upsert_from_response(self, phone, response_data, config=False, message=False):
        normalized_phone = self.normalize_phone(phone)
        user_id = self._extract_user_id(response_data)
        if not normalized_phone or not user_id:
            return self.browse()

        oa_id = config.oa_id if config else False
        recipient = self.search([
            ('phone', '=', normalized_phone),
            ('oa_id', '=', oa_id or False),
        ], limit=1)
        vals = {
            'phone': normalized_phone,
            'zalo_user_id': user_id,
            'oa_id': oa_id,
            'last_message_id': self._extract_message_id(response_data) or (message.zalo_msg_id if message else False),
            'last_sent_at': fields.Datetime.now(),
            'active': True,
        }
        if recipient:
            recipient.write(vals)
        else:
            recipient = self.create(vals)
        return recipient

    @api.model
    def _extract_user_id(self, response_data):
        for key, value in self._walk_response_items(response_data):
            normalized_key = (key or '').lower()
            if normalized_key in (
                'user_id',
                'uid',
                'zalo_user_id',
                'receiver_id',
                'user_id_by_oa',
                'user_id_by_app',
                'userid',
            ) and value:
                return str(value)
        return False

    @api.model
    def _extract_message_id(self, response_data):
        for key, value in self._walk_response_items(response_data):
            normalized_key = (key or '').lower()
            if normalized_key in ('msg_id', 'message_id', 'msgid') and value:
                return str(value)
        return False

    def _walk_response_items(self, value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key, item
                yield from self._walk_response_items(item)
        elif isinstance(value, list):
            for item in value:
                yield from self._walk_response_items(item)
