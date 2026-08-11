import base64
import json
import logging
from datetime import date, datetime, timezone

from markupsafe import Markup
from odoo import api, fields, models, tools
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.osv import expression


_logger = logging.getLogger(__name__)


class TicketHelpdesk(models.Model):
    _inherit = 'ticket.helpdesk'

    _ELE_AUT_API_BUSINESS_AREAS = {'AUT', 'ELE'}
    _ELE_AUT_API_FIELD_ATTRIBUTES = [
        'string',
        'help',
        'type',
        'relation',
        'relation_field',
        'selection',
        'required',
        'readonly',
        'store',
    ]
    _ELE_AUT_API_TECHNICAL_ONE2MANY_MODELS = {
        'ir.attachment',
        'mail.activity',
        'mail.followers',
        'mail.message',
    }
    _ELE_AUT_API_SENSITIVE_FIELDS = {
        'access_token',
        'api_key',
        'db_datas',
        'oauth_access_token',
        'password',
        'password_crypt',
        'signup_token',
        'store_fname',
        'totp_secret',
    }

    def _auto_init(self):
        result = super()._auto_init()
        tools.create_index(
            self._cr,
            'ticket_helpdesk_write_date_id_idx',
            self._table,
            ['write_date', 'id'],
        )
        return result

    @api.model
    def ele_aut_api_business_area_domain(self, business_areas=None):
        """Only accept the explicitly supported salesperson business areas."""
        requested_areas = (
            business_areas
            if business_areas is not None
            else self._ELE_AUT_API_BUSINESS_AREAS
        )
        normalized_areas = {
            str(getattr(area, 'value', area) or '').strip().upper()
            for area in requested_areas
        }
        normalized_areas &= self._ELE_AUT_API_BUSINESS_AREAS
        if not normalized_areas:
            return [('id', '=', 0)]
        return expression.OR([
            [('saleperson_id.sap_business_area', '=ilike', area)]
            for area in sorted(normalized_areas)
        ])

    def ele_aut_api_business_area_code(self):
        self.ensure_one()
        business_area = (
            self.sudo().saleperson_id.sap_business_area or ''
        ).strip().upper()
        if business_area in self._ELE_AUT_API_BUSINESS_AREAS:
            return business_area
        return False

    @api.model
    def ele_aut_api_find_ticket(self, identifier, business_areas=None):
        identifier = str(identifier or '').strip()
        if not identifier:
            return self.browse()

        identifier_domains = []
        if 'uuid' in self._fields:
            identifier_domains.append([('uuid', '=', identifier)])
        if 'name' in self._fields:
            identifier_domains.append([('name', '=', identifier)])
        if identifier.isdigit():
            identifier_domains.append([('id', '=', int(identifier))])
        if not identifier_domains:
            return self.browse()

        return self.with_context(active_test=False).search(
            expression.AND([
                expression.OR(identifier_domains),
                self.ele_aut_api_business_area_domain(business_areas),
            ]),
            limit=1,
        )

    @staticmethod
    def _ele_aut_api_normalize_datetime(value):
        if not value:
            return False
        value = fields.Datetime.to_datetime(value)
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.replace(microsecond=0)

    @api.model
    def _ele_aut_api_encode_cursor(
        self,
        snapshot_at,
        last_updated_at,
        last_id,
    ):
        payload = {
            'version': 1,
            'snapshot_at': fields.Datetime.to_string(snapshot_at),
            'last_updated_at': fields.Datetime.to_string(last_updated_at),
            'last_id': int(last_id),
        }
        raw_payload = json.dumps(
            payload,
            separators=(',', ':'),
            sort_keys=True,
        ).encode('utf-8')
        return base64.urlsafe_b64encode(raw_payload).decode('ascii').rstrip('=')

    @api.model
    def _ele_aut_api_decode_cursor(self, cursor):
        try:
            encoded_cursor = str(cursor or '').strip()
            encoded_cursor += '=' * (-len(encoded_cursor) % 4)
            payload = json.loads(
                base64.b64decode(
                    encoded_cursor.encode('ascii'),
                    altchars=b'-_',
                    validate=True,
                ).decode('utf-8'),
            )
            if not isinstance(payload, dict) or payload.get('version') != 1:
                raise ValueError
            snapshot_at = self._ele_aut_api_normalize_datetime(
                payload['snapshot_at'],
            )
            last_updated_at = self._ele_aut_api_normalize_datetime(
                payload['last_updated_at'],
            )
            last_id = int(payload['last_id'])
            if not snapshot_at or not last_updated_at or last_id <= 0:
                raise ValueError
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeError,
            json.JSONDecodeError,
        ) as error:
            raise ValueError('Invalid pagination cursor.') from error
        return snapshot_at, last_updated_at, last_id

    @api.model
    def ele_aut_api_search_tickets(
        self,
        query=None,
        statuses=None,
        business_areas=None,
        include_archived=False,
        updated_since=None,
        updated_until=None,
        cursor=None,
        offset=0,
        limit=20,
    ):
        server_time = self._ele_aut_api_normalize_datetime(
            fields.Datetime.now(),
        )
        updated_since = self._ele_aut_api_normalize_datetime(updated_since)
        requested_updated_until = self._ele_aut_api_normalize_datetime(
            updated_until,
        )
        if (
            updated_since
            and requested_updated_until
            and updated_since > requested_updated_until
        ):
            raise ValueError(
                'updated_since must be earlier than or equal to updated_until.',
            )

        cursor_updated_at = False
        cursor_id = False
        if cursor:
            if offset:
                raise ValueError('offset cannot be combined with cursor.')
            snapshot_at, cursor_updated_at, cursor_id = (
                self._ele_aut_api_decode_cursor(cursor)
            )
            if snapshot_at > server_time or cursor_updated_at > snapshot_at:
                raise ValueError('Invalid pagination cursor snapshot.')
            if (
                requested_updated_until
                and requested_updated_until != snapshot_at
            ):
                raise ValueError(
                    'updated_until does not match the cursor snapshot.',
                )
        else:
            snapshot_at = min(
                requested_updated_until or server_time,
                server_time,
            )
        if updated_since and updated_since > snapshot_at:
            raise ValueError(
                'updated_since must be earlier than or equal to the snapshot.',
            )

        domain = self.ele_aut_api_business_area_domain(business_areas)
        query = str(query or '').strip()
        if query:
            search_domains = [
                [(field_name, 'ilike', query)]
                for field_name in ('name', 'subject')
                if field_name in self._fields
            ]
            if 'customer_id' in self._fields:
                search_domains.append([('customer_id.name', 'ilike', query)])
            if search_domains:
                domain = expression.AND([
                    domain,
                    expression.OR(search_domains),
                ])
        if statuses and 'status' in self._fields:
            domain = expression.AND([
                domain,
                [('status', 'in', list(statuses))],
            ])

        if updated_since:
            domain = expression.AND([
                domain,
                [('write_date', '>=', updated_since)],
            ])
        domain = expression.AND([
            domain,
            [('write_date', '<=', snapshot_at)],
        ])

        ticket_model = self.with_context(active_test=not include_archived)
        total_count = ticket_model.search_count(domain)

        page_domain = domain
        if cursor_updated_at:
            page_domain = expression.AND([
                page_domain,
                expression.OR([
                    [('write_date', '>', cursor_updated_at)],
                    [
                        ('write_date', '=', cursor_updated_at),
                        ('id', '>', cursor_id),
                    ],
                ]),
            ])
        page_tickets = ticket_model.search(
            page_domain,
            offset=offset,
            limit=limit + 1,
            order='write_date asc, id asc',
        )
        has_more = len(page_tickets) > limit
        tickets = page_tickets[:limit]
        next_cursor = None
        if has_more and tickets:
            last_ticket = tickets[-1]
            next_cursor = self._ele_aut_api_encode_cursor(
                snapshot_at,
                last_ticket.write_date,
                last_ticket.id,
            )
        return {
            'tickets': tickets,
            'total_count': total_count,
            'has_more': has_more,
            'next_cursor': next_cursor,
            'snapshot_at': snapshot_at,
            'server_time': server_time,
            'updated_since': updated_since,
        }

    @staticmethod
    def _ele_aut_api_json_safe(value):
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, bytes):
            try:
                return value.decode('ascii')
            except UnicodeDecodeError:
                return base64.b64encode(value).decode('ascii')
        if isinstance(value, Markup):
            return str(value)
        if isinstance(value, dict):
            return {
                str(key): TicketHelpdesk._ele_aut_api_json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [
                TicketHelpdesk._ele_aut_api_json_safe(item)
                for item in value
            ]
        return str(value)

    @classmethod
    def _ele_aut_api_field_metadata(cls, raw_metadata):
        metadata = {
            key: cls._ele_aut_api_json_safe(value)
            for key, value in raw_metadata.items()
            if key != 'selection'
        }
        selection = raw_metadata.get('selection') or []
        if selection:
            metadata['selection'] = [
                {
                    'value': cls._ele_aut_api_json_safe(value),
                    'label': label,
                }
                for value, label in selection
            ]
        return metadata

    @staticmethod
    def _ele_aut_api_selection_label(raw_metadata, value):
        if value in (None, False):
            return None
        for option_value, option_label in raw_metadata.get('selection') or []:
            if option_value == value:
                return option_label
        return None

    def _ele_aut_api_readable_field_metadata(self, record):
        return {
            field_name: metadata
            for field_name, metadata in record.fields_get(
                allfields=None,
                attributes=self._ELE_AUT_API_FIELD_ATTRIBUTES,
            ).items()
            if field_name not in self._ELE_AUT_API_SENSITIVE_FIELDS
        }

    def _ele_aut_api_accessible_relation(self, record, field_name, field):
        relation_model = record.env[field.comodel_name].with_context(
            active_test=False,
        )
        try:
            if (
                field.comodel_name == 'ir.attachment'
                and field.type == 'one2many'
                and field.inverse_name == 'res_id'
                and 'res_model' in relation_model._fields
            ):
                return relation_model.search([
                    ('res_model', '=', record._name),
                    ('res_id', '=', record.id),
                ])

            related = record[field_name]
            if not related:
                return relation_model.browse()
            return relation_model.browse(related.ids).exists()
        except (AccessError, MissingError, UserError):
            return relation_model.browse()

    def _ele_aut_api_record_references(self, records):
        if not records:
            return []

        field_names = ['display_name']
        readable_fields = self._ele_aut_api_readable_field_metadata(records)
        if 'uuid' in readable_fields:
            field_names.append('uuid')
        try:
            values_by_id = {
                values['id']: values
                for values in records.read(field_names, load=None)
            }
        except (AccessError, MissingError, UserError):
            return []

        references = []
        for record in records:
            values = values_by_id.get(record.id, {})
            reference = {
                'id': record.id,
                'model': record._name,
                'display_name': values.get('display_name') or False,
            }
            if 'uuid' in field_names:
                reference['uuid'] = values.get('uuid') or False
            references.append(reference)
        return references

    def _ele_aut_api_serialize_relation(
        self,
        record,
        field_name,
        field,
        attachment_ids,
    ):
        related = self._ele_aut_api_accessible_relation(
            record,
            field_name,
            field,
        )
        if field.comodel_name == 'ir.attachment':
            attachment_ids.update(related.ids)

        references = self._ele_aut_api_record_references(related)
        if field.type == 'many2one':
            return references[0] if references else None
        return references

    def _ele_aut_api_read_scalar_values(
        self,
        record,
        scalar_field_names,
        include_binary,
    ):
        if not scalar_field_names:
            return {}, set()

        read_record = record if include_binary else record.with_context(
            bin_size=True,
        )
        try:
            return read_record.read(scalar_field_names, load=None)[0], set()
        except (AccessError, MissingError, UserError):
            values = {}
            unavailable_fields = set()
            for field_name in scalar_field_names:
                try:
                    values[field_name] = read_record.read(
                        [field_name],
                        load=None,
                    )[0].get(field_name)
                except (AccessError, MissingError, UserError) as error:
                    unavailable_fields.add(field_name)
                    _logger.info(
                        'ELE/AUT ticket API skipped %s.%s: %s',
                        record._name,
                        field_name,
                        type(error).__name__,
                    )
            return values, unavailable_fields

    def _ele_aut_api_serialize_record(
        self,
        record,
        include_binary,
        attachment_ids,
    ):
        record.ensure_one()
        raw_metadata = self._ele_aut_api_readable_field_metadata(record)
        data = {
            'id': record.id,
            'model': record._name,
        }
        display_values = {}
        field_metadata = {}
        scalar_field_names = [
            field_name
            for field_name in sorted(raw_metadata)
            if record._fields.get(field_name)
            and record._fields[field_name].type
            not in ('many2one', 'one2many', 'many2many')
        ]
        scalar_values, unavailable_fields = (
            self._ele_aut_api_read_scalar_values(
                record,
                scalar_field_names,
                include_binary,
            )
        )

        for field_name in sorted(raw_metadata):
            field = record._fields.get(field_name)
            if not field:
                continue

            metadata = raw_metadata[field_name]
            field_metadata[field_name] = self._ele_aut_api_field_metadata(
                metadata,
            )
            if field.type == 'binary':
                field_metadata[field_name]['binary_included'] = include_binary
            if field_name in unavailable_fields:
                field_metadata[field_name]['available'] = False
                data[field_name] = None
                continue
            try:
                if field.type in ('many2one', 'one2many', 'many2many'):
                    value = self._ele_aut_api_serialize_relation(
                        record,
                        field_name,
                        field,
                        attachment_ids,
                    )
                else:
                    value = self._ele_aut_api_json_safe(
                        scalar_values.get(field_name),
                    )
                data[field_name] = value

                if field.type == 'selection':
                    label = self._ele_aut_api_selection_label(metadata, value)
                    if label is not None:
                        display_values[field_name] = label
            except (AccessError, MissingError, UserError) as error:
                field_metadata[field_name]['available'] = False
                data[field_name] = None
                _logger.info(
                    'ELE/AUT ticket API skipped %s.%s: %s',
                    record._name,
                    field_name,
                    type(error).__name__,
                )

        return {
            'id': record.id,
            'model': record._name,
            'display_name': data.get('display_name') or False,
            'data': data,
            'display_values': display_values,
        }, field_metadata

    def _ele_aut_api_collection_payload(
        self,
        records,
        total_count,
        limit,
        include_binary,
        attachment_ids,
    ):
        selected_records = records[:limit]
        serialized_records = []
        field_metadata = {}
        for record in selected_records:
            serialized, record_metadata = self._ele_aut_api_serialize_record(
                record,
                include_binary,
                attachment_ids,
            )
            serialized_records.append(serialized)
            if not field_metadata:
                field_metadata = record_metadata

        return {
            'model': records._name,
            'count': total_count,
            'returned_count': len(serialized_records),
            'truncated': total_count > len(serialized_records),
            'field_metadata': field_metadata,
            'records': serialized_records,
        }

    def _ele_aut_api_related_payload(
        self,
        raw_ticket_metadata,
        include_binary,
        related_limit,
        attachment_ids,
    ):
        related_payload = {}
        for field_name in sorted(raw_ticket_metadata):
            field = self._fields.get(field_name)
            if (
                not field
                or field.type != 'one2many'
                or field.comodel_name
                in self._ELE_AUT_API_TECHNICAL_ONE2MANY_MODELS
            ):
                continue

            records = self._ele_aut_api_accessible_relation(
                self,
                field_name,
                field,
            )
            related_payload[field_name] = (
                self._ele_aut_api_collection_payload(
                    records,
                    len(records),
                    related_limit,
                    include_binary,
                    attachment_ids,
                )
            )
        return related_payload

    def _ele_aut_api_chatter_payload(
        self,
        include_chatter,
        include_binary,
        related_limit,
        attachment_ids,
    ):
        if not include_chatter:
            return {
                'messages': None,
                'activities': None,
            }

        definitions = {
            'messages': (
                'mail.message',
                [('model', '=', self._name), ('res_id', '=', self.id)],
                'date asc, id asc',
            ),
            'activities': (
                'mail.activity',
                [('res_model', '=', self._name), ('res_id', '=', self.id)],
                'date_deadline asc, id asc',
            ),
        }
        payload = {}
        for key, (model_name, domain, order) in definitions.items():
            model = self.env[model_name].with_context(active_test=False)
            try:
                total_count = model.search_count(domain)
                records = model.search(
                    domain,
                    order=order,
                    limit=related_limit,
                )
                payload[key] = self._ele_aut_api_collection_payload(
                    records,
                    total_count,
                    related_limit,
                    include_binary,
                    attachment_ids,
                )
            except (AccessError, MissingError, UserError):
                payload[key] = None
        return payload

    def _ele_aut_api_attachment_payload(
        self,
        attachment,
        include_binary,
        base_url,
    ):
        readable_fields = attachment.fields_get()
        field_names = [
            field_name
            for field_name in (
                'uuid',
                'name',
                'mimetype',
                'file_size',
                'type',
                'url',
                'public',
                'create_date',
                'write_date',
                'res_model',
                'res_id',
                'res_field',
                'checksum',
            )
            if field_name in readable_fields
        ]
        values = self._ele_aut_api_json_safe(
            attachment.read(field_names, load=None)[0],
        )
        values.update({
            'id': attachment.id,
            'model': attachment._name,
            'download_url': (
                '%s/web/content/%s?download=true' % (base_url, attachment.id)
                if attachment.type == 'binary'
                else attachment.url
            ),
            'data_base64': None,
        })
        if include_binary and attachment.type == 'binary':
            values['data_base64'] = self._ele_aut_api_json_safe(
                attachment.datas,
            )
        return values

    def _ele_aut_api_attachments_payload(
        self,
        attachment_ids,
        include_binary,
    ):
        attachment_model = self.env['ir.attachment'].with_context(
            active_test=False,
        )
        domain = [
            '|',
            ('id', 'in', sorted(attachment_ids)),
            '&',
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
        ]
        try:
            attachments = attachment_model.search(
                domain,
                order='create_date asc, id asc',
            )
        except (AccessError, MissingError, UserError):
            return []

        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url',
        ) or ''
        result = []
        for attachment in attachments:
            try:
                result.append(self._ele_aut_api_attachment_payload(
                    attachment,
                    include_binary,
                    base_url.rstrip('/'),
                ))
            except (AccessError, MissingError, UserError):
                continue
        return result

    def get_ele_aut_full_api_data(
        self,
        include_related=True,
        include_chatter=True,
        include_binary=False,
        related_limit=500,
    ):
        """Return a self-describing snapshot of an ELE/AUT ticket."""
        self.ensure_one()
        business_area = self.ele_aut_api_business_area_code()
        if not business_area:
            raise MissingError('The ticket is not in ELE or AUT.')

        attachment_ids = set()
        serialized_ticket, field_metadata = (
            self._ele_aut_api_serialize_record(
                self,
                include_binary,
                attachment_ids,
            )
        )
        raw_ticket_metadata = self._ele_aut_api_readable_field_metadata(self)
        related_records = {}
        if include_related:
            related_records = self._ele_aut_api_related_payload(
                raw_ticket_metadata,
                include_binary,
                related_limit,
                attachment_ids,
            )
        chatter = self._ele_aut_api_chatter_payload(
            include_chatter,
            include_binary,
            related_limit,
            attachment_ids,
        )
        attachments = self._ele_aut_api_attachments_payload(
            attachment_ids,
            include_binary,
        )

        return {
            'model': self._name,
            'business_area': business_area,
            'generated_at': self._ele_aut_api_json_safe(
                fields.Datetime.now(),
            ),
            'active': bool(getattr(self, 'active', True)),
            'created_at': self._ele_aut_api_json_safe(self.create_date),
            'updated_at': self._ele_aut_api_json_safe(self.write_date),
            'start_date': self._ele_aut_api_json_safe(
                getattr(self, 'start_date', False),
            ),
            'end_date': self._ele_aut_api_json_safe(
                getattr(self, 'end_date', False),
            ),
            'replied_date': self._ele_aut_api_json_safe(
                getattr(self, 'replied_date', False),
            ),
            'identifier': {
                'id': self.id,
                'uuid': getattr(self, 'uuid', False) or False,
                'name': getattr(self, 'name', False) or False,
            },
            'ticket': serialized_ticket,
            'field_metadata': field_metadata,
            'related_records': related_records,
            'chatter': chatter,
            'attachments': attachments,
        }
