import base64
import logging
import uuid
from urllib.parse import urlparse

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..business_days import add_business_days

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    ts_fault_description = fields.Text(string='Mô tả lỗi trên báo giá', copy=False)
    ts_sales_response = fields.Selection([
        ('pending', 'Chờ phản hồi'), ('received', 'Đã nhận phản hồi'),
    ], default='pending', copy=False, tracking=True)
    ts_sales_response_note = fields.Text(string='Nội dung phản hồi', copy=False, tracking=True)
    ts_quotation_generation = fields.Char(copy=False, readonly=True)
    ts_quotation_sent_at = fields.Datetime(string='Đã gửi email và Teams lúc', copy=False, readonly=True)
    ts_response_due_at = fields.Datetime(string='Hạn phản hồi (3 ngày làm việc)', copy=False, readonly=True, index=True)
    ts_reminder_queued_at = fields.Datetime(string='Đã tạo nhắc báo giá lúc', copy=False, readonly=True)
    ts_quotation_pdf_id = fields.Many2one('ir.attachment', copy=False, readonly=True, ondelete='set null')

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            ticket_id = values.get('ticket_id') or self.env.context.get('default_ticket_id')
            if ticket_id and 'ts_fault_description' not in values:
                ticket = self.env['ticket.helpdesk'].browse(ticket_id)
                values['ts_fault_description'] = ticket.product_error_note or ticket.product_error_description or ''
        return super().create(vals_list)

    @api.onchange('ticket_id')
    def _onchange_ts_fault_description(self):
        for order in self:
            if order.ticket_id and not order.ts_fault_description:
                order.ts_fault_description = order.ticket_id.product_error_note or order.ticket_id.product_error_description

    def _get_ts_fault_sections(self):
        """Keep merged quotation tickets and their serials independent."""
        sections = []
        seen = set()
        for order in self:
            tickets = order.ticket_id
            if 'ts_quotation_ticket_ids' in order._fields:
                tickets |= order.ts_quotation_ticket_ids
            for ticket in tickets:
                key = (order.id, ticket.id)
                text = (order.ts_fault_description if ticket == order.ticket_id else '') or ticket.product_error_note or ticket.product_error_description
                if text and key not in seen:
                    sections.append({'ticket': ticket.name, 'serial': ticket.stock_name or '', 'description': text})
                    seen.add(key)
            if not tickets and order.ts_fault_description:
                sections.append({'ticket': order.name, 'serial': '', 'description': order.ts_fault_description})
        return sections

    def _prepare_standard_quotation_summary_lines(self, ticket, lines):
        summary = super()._prepare_standard_quotation_summary_lines(ticket, lines)
        main_product = self._get_standard_quotation_ticket_product(ticket)
        main_lines = lines.filtered(lambda line: line.product_id == main_product)
        service_lines = lines.filtered(self._is_standard_quotation_service_line)
        component_lines = lines - main_lines - service_lines
        if component_lines:
            # The existing summary excludes PHIDICHVU when components exist.
            # Include both components and service fees in the repair amount.
            service_amount = sum(service_lines.mapped('price_subtotal'))
            summary[1]['price_unit'] += service_amount
            summary[1]['price_subtotal'] += service_amount
        return summary

    def _ts_sales_email(self):
        self.ensure_one()
        salesperson = self.ticket_id.saleperson_id
        email = salesperson.work_email or salesperson.user_id.email
        if not email or '@' not in email:
            raise UserError(_('Sale phụ trách báo giá %s chưa có email Microsoft hợp lệ.') % self.name)
        return email.strip()

    def _ts_check_webhook(self):
        params = self.env['ir.config_parameter'].sudo()
        if not params.get_param('ts_techservice_n8n.webhook_url') or not params.get_param('ts_techservice_n8n.webhook_token'):
            raise UserError(_('Cần cấu hình webhook n8n và token trong Thiết lập trước khi gửi.'))
        url = urlparse(params.get_param('ts_techservice_n8n.webhook_url'))
        if url.scheme != 'https' or not url.netloc:
            raise UserError(_('Webhook n8n phải là URL HTTPS hợp lệ.'))

    def _ts_due_at(self, sent_at):
        self.ensure_one()
        zone = pytz.timezone(self.company_id.resource_calendar_id.tz or 'Asia/Bangkok')
        local = pytz.UTC.localize(sent_at).astimezone(zone)
        raw = self.env['ir.config_parameter'].sudo().get_param('ts_techservice_n8n.holidays', '')
        try:
            holidays = [fields.Date.to_date(day.strip()) for day in raw.split(',') if day.strip()]
        except ValueError as error:
            raise UserError(_('Ngày nghỉ phải có định dạng YYYY-MM-DD.')) from error
        return add_business_days(local, holidays=holidays).astimezone(pytz.UTC).replace(tzinfo=None)

    def _ts_make_pdf(self):
        self.ensure_one()
        pdf, _format = self.env['ir.actions.report']._render_qweb_pdf(
            'dat_service_workflow_extension.action_report_standard_quotation', res_ids=self.ids,
        )
        return self.env['ir.attachment'].create({
            'name': self._get_standard_quotation_report_filename() + '.pdf',
            'type': 'binary', 'datas': base64.b64encode(pdf), 'mimetype': 'application/pdf',
            'res_model': self._name, 'res_id': self.id,
        })

    def action_send_standard_quotation_to_sales(self):
        self._ts_check_webhook()
        for order in self:
            if not order.ticket_id:
                raise UserError(_('Chỉ gửi qua n8n đối với báo giá có ticket TechService.'))
            if order.state == 'cancel' or order.status in ('cancelled', 'rejected'):
                raise UserError(_('Không gửi báo giá đã hủy.'))
            if order.ts_quotation_generation:
                raise UserError(_('Báo giá đã có lượt gửi. Xem trạng thái trong Hàng đợi thông báo; không nhấn gửi lại để tránh trùng.'))
            recipient = order._ts_sales_email()
            order._ts_due_at(fields.Datetime.now())  # Validate holidays before any delivery.
            # Capture faults and PDF once; reminders use exactly this quotation.
            if not order.ts_fault_description:
                order.ts_fault_description = order.ticket_id.product_error_note or order.ticket_id.product_error_description
            order.ts_quotation_generation = uuid.uuid4().hex
            order.ts_sales_response = 'pending'
            order.ts_quotation_pdf_id = order._ts_make_pdf()
            order._ts_enqueue_quotation('quotation_sent', recipient)
            order.message_post(body=_('Đã xếp hàng gửi báo giá qua email và Teams cho %s.') % recipient)
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'success', 'message': _('Đã xếp hàng gửi email và Teams.'), 'sticky': False},
        }

    def _ts_enqueue_quotation(self, event_type, recipient):
        self.ensure_one()
        title = (_('Nhắc phản hồi báo giá') if event_type == 'quotation_reminder' else _('Báo giá TechService')) + ' ' + self.name
        body = '%s\nTicket: %s\nModel: %s\nSerial: %s\nMô tả lỗi: %s\nVui lòng phản hồi trên TechService.' % (
            title, self.ticket_id.name, self.main_product_code or '', self.ticket_id.stock_name or '',
            self.ts_fault_description or '',
        )
        self.env['ts.n8n.notification'].sudo()._enqueue(
            event_key='%s:%s:%s' % (self.id, self.ts_quotation_generation, event_type),
            event_type=event_type, recipient=recipient, title=title, body=body,
            ticket=self.ticket_id, order=self, attachment=self.ts_quotation_pdf_id,
        )

    def action_ts_record_sales_response(self):
        for order in self:
            if not (order.ts_sales_response_note or '').strip():
                raise UserError(_('Nhập nội dung phản hồi trước khi xác nhận.'))
            order.ts_sales_response = 'received'
            order.env['ts.n8n.notification'].sudo().search([
                ('order_id', '=', order.id), ('event_type', '=', 'quotation_reminder'),
                ('state', 'in', ['pending', 'failed']),
            ]).write({'state': 'cancelled'})
            order.message_post(body=_('Đã ghi nhận phản hồi của sale: %s') % order.ts_sales_response_note)
            order.ticket_id._ts_close_alert_activity('quotation:%s' % order.id)
        return True

    def _ts_waiting_response(self):
        self.ensure_one()
        responded = self.service_quotation_status not in ('waiting_quotation', 'waiting_customer_approval')
        return (
            self.ts_sales_response == 'pending' and not responded
            and not self.ticket_id.sale_order_feedback and self.state not in ('sale', 'cancel')
            and self.status not in ('confirmed', 'cancelled', 'rejected')
            and self.ticket_id.status not in ('closed', 'rejected')
        )

    @api.model
    def _cron_ts_quotation_reminders(self):
        now = fields.Datetime.now()
        orders = self.search([
            ('ts_response_due_at', '<=', now), ('ts_quotation_sent_at', '!=', False),
            ('ts_sales_response', '=', 'pending'), ('ts_reminder_queued_at', '=', False),
            ('state', 'not in', ['sale', 'cancel']), ('status', 'not in', ['confirmed', 'cancelled', 'rejected']),
            ('service_quotation_status', 'in', ['waiting_quotation', 'waiting_customer_approval']),
            ('ticket_id.sale_order_feedback', '=', False), ('ticket_id.status', 'not in', ['closed', 'rejected']),
        ], limit=100)
        for order in orders:
            if not order._ts_waiting_response():
                continue
            try:
                with self.env.cr.savepoint():
                    order._ts_enqueue_quotation('quotation_reminder', order._ts_sales_email())
                    order.ts_reminder_queued_at = now
                    order.ticket_id._ts_raise_alert(
                        'quotation:%s' % order.id, _('Báo giá quá hạn phản hồi'),
                        _('Báo giá %s chưa được phản hồi sau 3 ngày làm việc. Đã tạo một lần nhắc sale qua email và Teams.') % order.name,
                    )
            except UserError:
                _logger.warning('Cannot queue quotation reminder for order %s: check sale email', order.id)
