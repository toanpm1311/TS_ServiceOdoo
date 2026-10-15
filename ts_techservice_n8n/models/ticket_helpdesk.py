from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.osv import expression


class TicketHelpdesk(models.Model):
    _inherit = 'ticket.helpdesk'

    ts_sla_alert_status_id = fields.Many2one('ticket.step.status', copy=False, readonly=True)
    ts_missing_so_alerted = fields.Boolean(copy=False, readonly=True)
    ts_sla_overdue = fields.Boolean(string='Quá hạn SLA', compute='_compute_ts_overdue', search='_search_ts_sla_overdue')
    ts_quotation_overdue = fields.Boolean(
        string='Báo giá quá hạn phản hồi', compute='_compute_ts_overdue', search='_search_ts_quotation_overdue',
    )
    ts_missing_return_so = fields.Boolean(
        string='Hoàn thành chưa có SO giao trả', compute='_compute_ts_missing_return_so',
        search='_search_ts_missing_return_so',
    )

    def _ts_missing_so_domain(self):
        delivery = self.env.ref('dat_website_helpdesk.step_wf1_product_delivery')
        return [
            ('step_id', '=', delivery.id), ('status', 'not in', ['closed', 'rejected']),
            ('sap_sale_order_number', '=', False),
            ('sale_order_ids', 'not any', [('sap_status', '!=', False), ('sap_status', '!=', '')]),
        ]

    def _ts_quotation_overdue_domain(self):
        return [
            ('sale_order_ids', 'any', [
                ('ts_response_due_at', '<=', fields.Datetime.now()), ('ts_quotation_sent_at', '!=', False),
                ('ts_sales_response', '=', 'pending'),
                ('service_quotation_status', 'in', ['waiting_quotation', 'waiting_customer_approval']),
                ('state', 'not in', ['sale', 'cancel']), ('status', 'not in', ['confirmed', 'cancelled', 'rejected']),
            ]),
            ('sale_order_feedback', '=', False), ('status', 'not in', ['closed', 'rejected']),
        ]

    def _compute_ts_overdue(self):
        now = fields.Datetime.now()
        for ticket in self:
            ticket.ts_sla_overdue = ticket.status == 'in_progress' and bool(ticket.ticket_step_status_ids.filtered(
                lambda status: status.step_id == ticket.step_id and status.status == 'in_progress'
                and status.deadline and status.deadline < now
            ))
            ticket.ts_quotation_overdue = any(
                order.ts_quotation_sent_at and order.ts_response_due_at and order.ts_response_due_at <= now
                and order._ts_waiting_response() for order in ticket.sale_order_ids
            )

    def _ts_boolean_search_domain(self, domain, operator, value):
        if operator not in ('=', '!='):
            raise NotImplementedError('Only boolean equality is supported')
        return domain if (operator == '=') == bool(value) else ['!'] + expression.normalize_domain(domain)

    def _search_ts_sla_overdue(self, operator, value):
        statuses = self.env['ticket.step.status'].search([
            ('status', '=', 'in_progress'), ('deadline', '<', fields.Datetime.now()),
            ('ticket_id.status', '=', 'in_progress'),
        ]).filtered(lambda status: status.step_id == status.ticket_id.step_id)
        return self._ts_boolean_search_domain([('id', 'in', statuses.ticket_id.ids)], operator, value)

    def _search_ts_quotation_overdue(self, operator, value):
        return self._ts_boolean_search_domain(self._ts_quotation_overdue_domain(), operator, value)

    def _compute_ts_missing_return_so(self):
        matches = self.search(expression.AND([[('id', 'in', self.ids)], self._ts_missing_so_domain()]))
        for ticket in self:
            ticket.ts_missing_return_so = ticket in matches

    def _search_ts_missing_return_so(self, operator, value):
        return self._ts_boolean_search_domain(self._ts_missing_so_domain(), operator, value)

    def _ts_alert_users(self):
        self.ensure_one()
        return (self.assigned_user_id | self.department_id.manager_id.user_id).filtered(lambda user: user.active)

    def _ts_close_alert_activity(self, key):
        self.ensure_one()
        self.env['mail.activity'].sudo().search([
            ('res_model', '=', self._name), ('res_id', '=', self.id),
            ('summary', '=', '[TS:%s]' % key),
        ]).action_feedback(feedback=_('Đã xử lý cảnh báo.'))

    def _ts_raise_alert(self, key, title, body):
        self.ensure_one()
        users = self._ts_alert_users()
        summary = '[TS:%s]' % key
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        for user in users:
            existing = self.env['mail.activity'].sudo().search([
                ('res_model', '=', self._name), ('res_id', '=', self.id),
                ('summary', '=', summary), ('user_id', '=', user.id),
            ], limit=1)
            if not existing:
                self.activity_schedule(
                    activity_type_id=activity_type.id, user_id=user.id, summary=summary,
                    note=Markup('<b>%s</b><p>%s</p>') % (title, body),
                )
        self.message_post(body=Markup('<b>%s</b><p>%s</p>') % (title, body), partner_ids=users.partner_id.ids)
        for user in users:
            email = user.employee_id.work_email or user.email
            if email and '@' in email:
                self.env['ts.n8n.notification'].sudo()._enqueue(
                    event_key='%s:%s:%s' % (self.id, key, user.id), event_type='ticket_alert',
                    recipient=email, title=title, body=body, ticket=self,
                )

    @api.model
    def _cron_ts_ticket_alerts(self):
        now = fields.Datetime.now()
        statuses = self.env['ticket.step.status'].search([
            ('status', '=', 'in_progress'), ('deadline', '<', now),
            ('ticket_id.status', '=', 'in_progress'),
            ('ts_overdue_alerted', '=', False),
        ]).filtered(lambda status: status.step_id == status.ticket_id.step_id)[:100]
        for status in statuses:
            ticket = status.ticket_id
            if ticket.step_id != status.step_id or ticket.ts_sla_alert_status_id == status:
                continue
            ticket._ts_raise_alert(
                'sla:%s' % status.id, _('Quá hạn SLA bước xử lý'),
                _('Ticket %(ticket)s quá hạn bước %(step)s, hạn SLA: %(deadline)s.') % {
                    'ticket': ticket.name, 'step': status.step_id.name,
                    'deadline': fields.Datetime.context_timestamp(ticket.with_context(tz='Asia/Bangkok'), status.deadline),
                },
            )
            ticket.ts_sla_alert_status_id = status
            status.ts_overdue_alerted = True
        for ticket in self.search(self._ts_missing_so_domain() + [('ts_missing_so_alerted', '=', False)], limit=500):
            if ticket.ts_missing_so_alerted:
                continue
            ticket._ts_raise_alert(
                'return_so', _('Hoàn thành nhưng chưa có SO giao trả'),
                _('Ticket %s đã đến bước giao trả sản phẩm nhưng chưa có SO SAP.') % ticket.name,
            )
            ticket.ts_missing_so_alerted = True


class TicketStepStatus(models.Model):
    _inherit = 'ticket.step.status'

    ts_overdue_alerted = fields.Boolean(copy=False, readonly=True)
