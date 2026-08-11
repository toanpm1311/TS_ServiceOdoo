import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ZaloZnsMessage(models.Model):
    _inherit = 'zalo.zns.message'

    helpdesk_ticket_id = fields.Many2one(
        'ticket.helpdesk',
        string='Ticket',
        tracking=True,
        help='Ticket used to fill template parameters for ZNS messages.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        ticket_model = self.env['ir.model']._get('ticket.helpdesk')
        for vals in vals_list:
            ticket_id = vals.get('helpdesk_ticket_id')
            if ticket_id:
                ticket = self.env['ticket.helpdesk'].browse(ticket_id)
                vals.update(self._prepare_ticket_values(ticket, ticket_model))
        return super().create(vals_list)

    def write(self, vals):
        if 'helpdesk_ticket_id' in vals and vals.get('helpdesk_ticket_id'):
            ticket = self.env['ticket.helpdesk'].browse(vals['helpdesk_ticket_id'])
            vals.update(self._prepare_ticket_values(ticket))
        return super().write(vals)

    def _prepare_ticket_values(self, ticket, ticket_model=False):
        ticket_model = ticket_model or self.env['ir.model']._get('ticket.helpdesk')
        phone = ticket.customer_phone
        return {
            'model_id': ticket_model.id,
            'record_id': ticket.id,
            'phone': phone,
            'name': ticket.name or ticket.display_name,
        }

    def _get_helpdesk_ticket(self):
        self.ensure_one()
        if self.helpdesk_ticket_id:
            return self.helpdesk_ticket_id.exists()
        if self.model_id.model == 'ticket.helpdesk' and self.record_id:
            return self.env['ticket.helpdesk'].browse(self.record_id).exists()
        return self.env['ticket.helpdesk']

    def _format_zns_date(self, value=False):
        if not value:
            value = fields.Date.context_today(self)
        if hasattr(value, 'date'):
            value = value.date()
        return value.strftime('%d/%m/%Y')

    def _add_zns_days(self, value=False, days=0):
        if not value:
            value = fields.Date.context_today(self)
        if hasattr(value, 'date'):
            value = value.date()
        return value + timedelta(days=days)

    def _clean_contact_name(self, value):
        value = re.sub(r'\s+', ' ', str(value or '')).strip()
        if not value:
            return ''

        candidates = [value]
        if ',' in value:
            candidates = [part.strip() for part in value.split(',') if part.strip()] + candidates

        for candidate in reversed(candidates):
            match = re.search(
                r'(?i)\b(anh|chị|chi)\s+[^,;/|()]+',
                candidate,
            )
            if match:
                contact_name = match.group(0).strip()
                contact_name = re.split(
                    r'(?i)\b(sdt|sđt|dt|đt|dien thoai|điện thoại)\b',
                    contact_name,
                )[0]
                return contact_name.strip()

        return candidates[-1]

    def _ticket_contact_name(self, ticket):
        for value in (
            ticket.customer_contact_name,
            ticket.owner_id.name,
            ticket.customer_id.name,
        ):
            contact_name = self._clean_contact_name(value)
            if contact_name:
                return contact_name
        return ticket.name or ticket.display_name

    def _fit_zns_text(self, value, max_length=False):
        value = str(value or '').strip()
        if max_length and len(value) > max_length:
            return value[:max_length].strip()
        return value

    def _complete_ticket_template_data(self, template_data, ticket):
        if not ticket:
            return template_data

        fallback_values = {
            'contactname': self._fit_zns_text(self._ticket_contact_name(ticket), 30),
            'sochungtu': ticket.name or ticket.display_name,
            'ngaygiaohang': self._format_zns_date(ticket.approved_date or ticket.end_date),
            'code': ticket.name or ticket.display_name,
            'date': self._format_zns_date(ticket.delivery_expected_date),
            'serialnumber': ticket.stock_name or ticket.stock_lot_id.name or '',
            'itemname': ticket.product_id.display_name or '',
            'timefinishexpected': self._format_zns_date(self._add_zns_days(ticket.create_date, 1)),
            'timedeliveryexpected': 'Giao hàng từ 1-3 ngày làm việc',
        }
        for key, value in fallback_values.items():
            if not template_data.get(key):
                template_data[key] = value
        template_data['serialnumber'] = fallback_values['serialnumber']
        template_data['timefinishexpected'] = fallback_values['timefinishexpected']
        template_data['timedeliveryexpected'] = fallback_values['timedeliveryexpected']
        if template_data.get('contactname'):
            template_data['contactname'] = self._fit_zns_text(template_data['contactname'], 30)
        return template_data

    def prepare_template_data(self):
        self.ensure_one()
        template_data = super().prepare_template_data()
        ticket = self._get_helpdesk_ticket()
        if ticket or self.template_id.model_id.model == 'ticket.helpdesk':
            template_data = self._complete_ticket_template_data(template_data, ticket)
        return template_data

    @api.onchange('helpdesk_ticket_id')
    def _onchange_helpdesk_ticket_id(self):
        for rec in self:
            if not rec.helpdesk_ticket_id:
                continue
            vals = rec._prepare_ticket_values(rec.helpdesk_ticket_id)
            rec.model_id = vals['model_id']
            rec.record_id = vals['record_id']
            rec.phone = vals['phone']
            rec.name = vals['name']

    @api.onchange('template_id')
    def _onchange_template_id(self):
        for rec in self:
            if rec.template_id.model_id.model == 'ticket.helpdesk' and rec.record_id:
                rec.helpdesk_ticket_id = self.env['ticket.helpdesk'].browse(rec.record_id)

    def _validate_template_record(self):
        self.ensure_one()
        if self.template_id.model_id.model == 'ticket.helpdesk' and not self.helpdesk_ticket_id:
            if self.model_id and self.model_id.model == 'ticket.helpdesk' and self.record_id:
                self.helpdesk_ticket_id = self.env['ticket.helpdesk'].browse(self.record_id)
            else:
                raise UserError(_('Please select a Ticket before sending this ZNS template.'))
        return super()._validate_template_record()
