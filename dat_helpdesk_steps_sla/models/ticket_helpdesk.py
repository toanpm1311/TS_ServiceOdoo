from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round
import logging

_logger = logging.getLogger(__name__)

class TicketHelpDesk(models.Model):
    _inherit = 'ticket.helpdesk'

    WORKFLOW_1 = 'dat_website_helpdesk.workflow_1'
    WORKFLOW_2 = 'dat_website_helpdesk.workflow_2'
    WORKFLOW_3 = 'dat_website_helpdesk.workflow_3'
    WORKFLOW_4 = 'dat_website_helpdesk.workflow_4'

    WORKFLOW_4_STEP_2 = 'dat_website_helpdesk.step_wf4_receiving_and_inspection'

    ticket_step_ids = fields.Many2many('ticket.step', string='Steps', compute='_compute_step_ids')
    ticket_step_status_ids = fields.One2many('ticket.step.status', 'ticket_id',
                                             string='Status', compute='_compute_ticket_step_status_ids',
                                             store=True, readonly=False)
    last_step_status = fields.Selection(
        selection=[
            ('not_started', 'Not Started'),
            ('in_progress', 'In Progress'),
            ('on_hold', 'On Hold'),
            ('done', 'Done'),
            ('rejected', 'Rejected')],
        compute='_compute_step_status',
        readonly=False,
        store=True)
    deadline = fields.Datetime(string='Deadline', readonly=True)
    waiting_for_assignment = fields.Boolean(compute='_compute_waiting_for_assignment', store=True)
    kpi_coefficient_ids = fields.One2many('kpi.coefficient', 'ticket_id', string='KPI Coefficient',
                                          compute='_compute_kpi_coefficient_ids', store=True)
    existing_kpi_user_ids = fields.Many2many('res.users', string='Existing KPI Users',
                                             compute='_compute_existing_kpi_user_ids')
    existing_assigned_user_ids = fields.Many2many('res.users', string='Existing KPI Users',
                                                  compute='_compute_existing_assigned_user_ids')
    task_allocation_ids = fields.One2many('task.allocation', 'ticket_id', string='Task Allocation',
                                          compute='_compute_task_allocation_ids', store=True)

    @api.depends('last_step_status')
    def _compute_step_status(self):
        for rec in self:
            if rec.last_step_status:
                rec.last_step_status = rec.ticket_step_status_ids[-1].status

    @api.onchange('assigned_user_id', 'assigned_follower_ids')
    def _onchange_assigned_user_id(self):
        for rec in self:
            if not rec.ticket_step_status_ids or rec.step_id in (self.env.ref(self.WORKFLOW_1_STEP_2),
                                                                 self.env.ref(self.WORKFLOW_2_STEP_2),
                                                                 self.env.ref(self.WORKFLOW_3_STEP_2),
                                                                 self.env.ref(self.WORKFLOW_4_STEP_2)):
                continue
            last_step = rec.ticket_step_status_ids[-1]
            user_ids = self.get_assigned_user_id_and_assigned_follower_ids(rec.assigned_user_id,
                                                                           rec.assigned_follower_ids)
            last_step.assignee_ids = [(6, 0, user_ids)]

    @api.depends('ticket_step_status_ids.assignee_ids')
    def _compute_existing_assigned_user_ids(self):
        for rec in self:
            rec.existing_assigned_user_ids = rec.ticket_step_status_ids.assignee_ids

    @api.depends('ticket_step_status_ids.assignee_ids')
    def _compute_task_allocation_ids(self):
        for rec in self:
            if rec.step_id in (self.env.ref(self.WORKFLOW_3_STEP_6)):
                current_status = rec.ticket_step_status_ids[-1]
                assigned_user_to_add = set(current_status.assignee_ids.ids) - set(rec.task_allocation_ids.user_id.ids)

                assigned_user_to_remove = set(rec.task_allocation_ids.user_id.ids) - set(
                    current_status.assignee_ids.ids)

                if assigned_user_to_add:
                    rec.task_allocation_ids = [(0, 0, {
                        'user_id': user_id,
                    }) for user_id in assigned_user_to_add]

                if assigned_user_to_remove:
                    rec.task_allocation_ids = [(2, line.id, 0) for line in rec.task_allocation_ids if
                                               line.user_id.id in assigned_user_to_remove]

            if rec.task_allocation_ids:
                rec._update_task_allocation_sequence()

    def _update_task_allocation_sequence(self):
        for ticket in self:
            allocation = 1/ len(ticket.task_allocation_ids)
            sequence = 1
            for line in ticket.task_allocation_ids:
                line.weight = allocation
                if line.sequence != sequence:
                    line.sequence = sequence
                sequence += 1

    @api.depends('kpi_coefficient_ids.user_id')
    def _compute_existing_kpi_user_ids(self):
        for rec in self:
            rec.existing_kpi_user_ids = rec.kpi_coefficient_ids.user_id

    @api.depends('ticket_step_status_ids')
    def _compute_kpi_coefficient_ids(self):
        for rec in self:
            if rec.ticket_step_status_ids:
                for user_id in rec.ticket_step_status_ids.mapped('assignee_ids'):
                    if user_id not in rec.kpi_coefficient_ids.mapped('user_id'):
                        rec.kpi_coefficient_ids = [(0, 0, {
                            'user_id': user_id.id,
                        })]

    email_assignee_sent = fields.Boolean(string="Assignee Email Sent", default=False)
    email_leader_sent = fields.Boolean(string="Leader Email Sent", default=False)

    @api.depends('step_id', 'ticket_step_status_ids')
    def _compute_waiting_for_assignment(self):
        for rec in self:
            rec.waiting_for_assignment = False
            if rec.ticket_step_status_ids:
                if (not rec.step_id
                        or rec.step_id.id in (self.env.ref('dat_website_helpdesk.step_wf1_receiving_and_inspection').id,
                                              self.env.ref('dat_website_helpdesk.step_wf4_receiving_and_inspection').id)
                        and len(rec.ticket_step_status_ids.filtered_domain([('step_id', '=', rec.step_id.id)])) != 0
                        and rec.ticket_step_status_ids.filtered_domain([('step_id', '=', rec.step_id.id)])[
                            -1].status == 'not_started'):
                    rec.waiting_for_assignment = True

    @api.depends('ticket_step_status_ids')
    def _compute_step_ids(self):
        for rec in self:
            rec.ticket_step_ids = rec.ticket_step_status_ids.step_id

    @api.depends('workflow_id', 'priority_id', 'create_date')
    def _compute_ticket_step_status_ids(self):
        for rec in self:
            if not rec.ticket_step_status_ids:
                user_ids = self.get_assigned_user_id_and_assigned_follower_ids(rec.assigned_user_id,
                                                                               rec.assigned_follower_ids)
                vals = {
                    'assignee_ids': [(6, 0, user_ids)],
                    'step_id': rec.step_id.id,
                    'start_date': fields.Datetime.now(),
                    'status': 'in_progress',
                }

                rec.ticket_step_status_ids = [(0, 0, vals)]

            for ticket_step_status_id in rec.ticket_step_status_ids:
                if ticket_step_status_id.status == 'in_progress':
                    ticket_step_status_id.action_compute_deadline()
                    rec.deadline = ticket_step_status_id.deadline

    def create_status_and_send_notification(self, is_reassign=False):
        self.action_create_status(is_reassign)
        self._send_email_notifications()
        self.sudo().write({
            'email_assignee_sent': False,
            'email_leader_sent': False
        })

    def action_assigned(self, new_user_id):
        super().action_assigned(new_user_id)
        self.create_status_and_send_notification()

    def action_next_step(self):
        self.ensure_one()

        _logger.info(
            "[TICKET][NEXT_STEP][START] ticket_id=%s ticket=%s step_id=%s step=%s popup_before=%s",
            self.id,
            self.name,
            self.step_id.id if self.step_id else False,
            self.step_id.name if self.step_id else False,
            self.popup_notification,
        )

        try:
            _logger.info(
                "[TICKET][NEXT_STEP][ZALO][BEFORE] ticket=%s",
                self.name,
            )
            self._send_zalo_notifications()
            _logger.info(
                "[TICKET][NEXT_STEP][ZALO][AFTER] ticket=%s",
                self.name,
            )

            _logger.info(
                "[TICKET][NEXT_STEP][SUPER][BEFORE] ticket=%s current_step=%s",
                self.name,
                self.step_id.name if self.step_id else False,
            )
            res = super().action_next_step()
            _logger.info(
                "[TICKET][NEXT_STEP][SUPER][AFTER] ticket=%s result=%s new_step=%s popup=%s",
                self.name,
                res,
                self.step_id.name if self.step_id else False,
                self.popup_notification,
            )

            if res:
                _logger.info(
                    "[TICKET][NEXT_STEP][RETURN_SUPER] ticket=%s return=%s",
                    self.name,
                    res,
                )
                return res

            if self.step_id in [self.env.ref(self.WORKFLOW_4_STEP_FOLLOW_UP)]:
                _logger.info(
                    "[TICKET][NEXT_STEP][FOLLOW_UP] ticket=%s => mark_step_done_and_close_ticket",
                    self.name,
                )
                self.mark_step_done_and_close_ticket()
                _logger.info(
                    "[TICKET][NEXT_STEP][FOLLOW_UP][DONE] ticket=%s",
                    self.name,
                )
            else:
                _logger.info(
                    "[TICKET][NEXT_STEP][CREATE_STATUS][BEFORE] ticket=%s step=%s",
                    self.name,
                    self.step_id.name if self.step_id else False,
                )
                self.create_status_and_send_notification()
                _logger.info(
                    "[TICKET][NEXT_STEP][CREATE_STATUS][AFTER] ticket=%s popup=%s",
                    self.name,
                    self.popup_notification,
                )

            # Popup thông báo khi tạo SO,DXVT thành công trên SAP
            if self.popup_notification:
                message = self.popup_notification
                _logger.info(
                    "[TICKET][NEXT_STEP][POPUP] ticket=%s message=%s",
                    self.name,
                    message,
                )
                self.popup_notification = False
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': message,
                        'type': 'success',
                        'sticky': False,
                        'next': {
                            'type': 'ir.actions.act_window',
                            'res_model': 'ticket.helpdesk',
                            'res_id': self.id,
                            'view_mode': 'form',
                            'views': [(False, 'form')],
                            'target': 'current',
                        }
                    }
                }

            _logger.info(
                "[TICKET][NEXT_STEP][END] ticket=%s no_popup_return",
                self.name,
            )

        except Exception as e:
            _logger.exception(
                "[TICKET][NEXT_STEP][ERROR] ticket_id=%s ticket=%s step=%s error=%s",
                self.id,
                self.name,
                self.step_id.name if self.step_id else False,
                e,
            )
            raise

    def mark_step_done_and_close_ticket(self):
        self.status = 'closed'
        self.end_date = fields.Datetime.now()
        self.ticket_step_status_ids.filtered(lambda status: status.status == 'in_progress').write(
            {'status': 'done'})
        self._send_zalo_notifications()

    def action_return_step(self, return_step_reason=False):
        super().action_return_step()
        if self.step_id in (self.env.ref(self.WORKFLOW_3_STEP_4), self.env.ref(self.WORKFLOW_3_STEP_6), self.env.ref(self.WORKFLOW_4_STEP_7)):
            self.assigned_user_id = \
                self.ticket_step_status_ids.filtered(lambda status: status.step_id.id == self.step_id.id).sorted(
                    key=lambda status: status.start_date, reverse=True)[0].assignee_ids[0]
        self.create_status_and_send_notification()

    def action_next_step_wf3_step9_provide_quotation(self):
        if self.quotation_approval_result in ('resurvey', 'change_technical_solution'):
            if self.quotation_approval_result == 'resurvey':
                self.step_id = self.env.ref(self.WORKFLOW_3_STEP_3)
            elif self.quotation_approval_result == 'change_technical_solution':
                self.step_id = self.env.ref(self.WORKFLOW_3_STEP_6)
            self.assigned_user_id = \
                self.ticket_step_status_ids.filtered(lambda status: status.step_id.id == self.step_id.id).sorted(
                    key=lambda status: status.start_date, reverse=True)[0].assignee_ids[0]
        super().action_next_step_wf3_step9_provide_quotation()

    def action_next_step_wf4_step7_acceptance_completion(self):
        for ticket in self:
            all_user_ids = ticket.ticket_step_status_ids.mapped('assignee_ids.id')
            distinct_user_ids = list(set(all_user_ids))
            existing_user_ids = ticket.task_allocation_ids.mapped('user_id.id')
            new_user_ids = [uid for uid in distinct_user_ids if uid not in existing_user_ids]
            lines = [(0, 0, {'user_id': uid}) for uid in new_user_ids]
            if lines:
                ticket.write({'task_allocation_ids': lines})
                if len(ticket.task_allocation_ids) == 1:
                    ticket.task_allocation_ids.weight = 1
                else:
                    ticket.task_allocation_ids.write({'weight': 0})
                ticket._update_task_allocation_sequence()

        super().action_next_step_wf4_step7_acceptance_completion()

    def action_create_status(self, is_reassign=False):
        current_status = self.ticket_step_status_ids.filtered(lambda status: status.status == 'in_progress')
        current_status.write({'status': 'done'})
        if (self.step_id == self.env.ref(self.WORKFLOW_4_STEP_7) and self.need_button_approve) or \
                (self.step_id == self.env.ref(self.WORKFLOW_3_STEP_9) and self.status == 'closed'):
            return

        user_ids = self.get_assigned_user_id_and_assigned_follower_ids(self.assigned_user_id,
                                                                       self.assigned_follower_ids)

        vals = {
            'step_id': self.step_id.id,
            'ticket_id': self.id,
            'assignee_ids': [(6, 0, user_ids)],
            'start_date': fields.Datetime.now(),
            'status': 'in_progress',
        }
        if is_reassign and current_status:
            vals.update({
                'time_sla': current_status.time_sla,
                'deadline': current_status.deadline,
                'time_alert': current_status.time_alert,
            })

        status_id = self.env['ticket.step.status'].create(vals)
        if not (is_reassign and current_status):
            status_id.action_compute_deadline()

        write_vals = {
            'deadline': status_id.deadline,
        }
        if not is_reassign:
            write_vals['start_date'] = status_id.start_date

        self.sudo().write(write_vals)

    def get_assigned_user_id_and_assigned_follower_ids(self, user_id=False, follower_ids=False):
        user_ids = []
        if user_id:
            user_ids.append(user_id.id)
        if follower_ids:
            user_ids += follower_ids.ids
        return user_ids

    def action_reception(self):
        super().action_reception()
        self.create_status_and_send_notification()

    def action_reject(self, reject_reason=False):
        super().action_reject(reject_reason)
        self.ticket_step_status_ids.filtered(lambda status: status.status != 'done').write({'status': 'rejected'})

        if self.parent_id:
            self.parent_id.ticket_step_status_ids.filtered(lambda status: status.status == 'in_progress').write(
                {'status': 'rejected'})

    def action_hold(self, on_hold_reason=False, next_expected_survey_date=False):
        super().action_hold(on_hold_reason, next_expected_survey_date)
        self.ticket_step_status_ids.filtered(lambda status: status.status == 'in_progress').write(
            {'status': 'on_hold', 'hold_date': fields.Datetime.now()})

    def action_continue(self):
        super().action_continue()
        hold_status_id = self.ticket_step_status_ids.filtered(lambda status: status.status == 'on_hold')
        hold_status_id.status = 'in_progress'
        resource_calendar = hold_status_id.assignee_ids[0].resource_calendar_id or hold_status_id.assignee_ids[
            0].company_id.resource_calendar_id
        if resource_calendar:
            resource_id = hold_status_id.assignee_ids[0].employee_ids.filtered(
                lambda x: x.company_id.id == hold_status_id.ticket_id.branch.id).resource_id
            hold_status_id.hold_time += \
                resource_calendar.get_work_duration_data_with_resource(hold_status_id.hold_date, fields.Datetime.now(),
                                                                       compute_leaves=True, resource=resource_id)[
                    'hours']
        hold_status_id.hold_date = False
        hold_status_id.action_compute_deadline()
        self.deadline = hold_status_id.deadline

    def action_reassign(self, new_user_id):
        super().action_reassign(new_user_id)
        self.create_status_and_send_notification(is_reassign=True)

    def action_approved(self):
        if self.workflow_id == self.env.ref(self.WORKFLOW_2) and False in self.kpi_coefficient_ids.mapped(
                'coefficient'):
            raise UserError(_("Please select a coefficient for all users before approving."))
        total = sum(self.task_allocation_ids.mapped('weight'))
        if self.workflow_id == self.env.ref(self.WORKFLOW_4) and float_compare(total, 1, precision_digits=2) != 0:
            raise UserError(_(
                "Tổng trọng số phân bổ phải bằng 100%% trước khi phê duyệt. "
                "Hiện tại là %s%%."
            ) % float_round(total*100, 2))
        super().action_approved()
        self.ticket_step_status_ids.filtered(lambda status: status.status == 'in_progress').write({'status': 'done'})
        self._send_zalo_notifications()

    @property
    def waiting_for_assignment_invisible_fields(self):
        visible_fields = {
            # general info
            'name',
            'assigned_user_id',
            'waiting_for_assignment',
            'priority_id',
            'step_id',
            'start_date',
            'end_date',
            'deadline',
            'ticket_type_id_domain',
            # ticket details
            'branch',
            'state_id',
            'subject',
            'description',
            'delivery_address',
            'department_id',
            'ticket_type_id',
            # product info
            'stock_lot_id',
            'product_id',
            'product_error_note',
            'product_warranty_status',
            'number_of_warranty',
            'ticket_product_image_ids',
            # requester info
            'customer_id',
            'customer_code',
            'customer_contact_name',
            'customer_company_name',
            'customer_phone',
            'customer_email',
            'customer_address',
            # owner info
            'owner_id',
            'owner_phone',
            'owner_email',
            'owner_address',
            # progress info
            'ticket_step_status_ids',
        }
        invisible_fields = set(self._fields.keys()).difference(visible_fields)
        return invisible_fields

    def _invisible_waiting_for_assignment_fields_in_form_view(self, arch, view):
        for field in arch.xpath("//sheet//field[not(ancestor::field)]"):
            fname = field.attrib.get('name')
            if fname not in self.waiting_for_assignment_invisible_fields:
                continue
            attr_val = field.attrib.get('invisible', '0')
            field.set('invisible', attr_val + ' or waiting_for_assignment')

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form':
            self._invisible_waiting_for_assignment_fields_in_form_view(arch, view)
        return arch, view

    @api.model_create_multi
    def create(self, vals_list):
        res = super(TicketHelpDesk, self).create(vals_list)
        for rec in res:
            if rec.workflow_id.id != self.env.ref(self.WORKFLOW_1).id:
                rec.ticket_step_status_ids.write({'status': 'in_progress'})
                rec.ticket_step_status_ids.action_compute_deadline()
                rec.start_date = rec.ticket_step_status_ids[0].start_date
                rec.deadline = rec.ticket_step_status_ids[0].deadline
        return res

    def _send_email_notifications(self):
        if self.step_id:
            leader_of_department = self.get_assigned_user_id_based_on_department(department=self.department_id, branch=self.branch, ticket_type=self.ticket_type_id, stock_lot=self.stock_lot_id)
            assigned_user_id = self.assigned_user_id
            if assigned_user_id == leader_of_department:
                if self.step_id.notify_assignee_email_on_enter:
                    self._send_assignee_email_on_enter()
            else:
                if self.step_id.notify_assignee_email_on_enter:
                    self._send_assignee_email_on_enter()
                if self.step_id.notify_leader_email_on_enter:
                    self._send_leader_email_on_enter()

    def _send_zalo_notifications(self):
        if self.status == 'closed' and self.workflow_id and self.workflow_id.template_zalo_review:
            self._send_zalo_notification_to_customer(self.workflow_id.template_zalo_review.id)
        elif self.status != 'closed' and self.step_id and self.step_id.notify_zalo and self.step_id.template_zalo:
            self._send_zalo_notification_to_customer(self.step_id.template_zalo.id)

    def _send_zalo_notification_to_customer(self, template_id):
        record = self.env['zalo.zns.message'].create({
            'name': _('Send zalo notification for step "%s" in ticket "%s".') % (self.step_id.name, self.name),
            'model_id': self.env['ir.model'].search([('model', '=', self._name)], limit=1).id,
            'record_id': self.id,
            'template_id': template_id,
            'phone': self.customer_phone,
        })
        record.action_send_message_zalo_zns()

    def _get_email_from(self):
        icp = self.env['ir.config_parameter'].sudo()
        alias = icp.get_param('mail.catchall.alias') or 'no-reply'
        domain = icp.get_param('mail.catchall.domain') or 'yourcompany.com'
        return '"Odoo Bot" <%s@%s>' % (alias, domain)

    def _send_for_ticket(self, ticket, template_field, get_users, ctx_key, email_from):
        template = getattr(ticket.step_id, template_field)
        if not template:
            raise UserError(_(
                "Bạn cần thiết lập email template %s trên bước: %s"
            ) % (template_field, ticket.step_id.name))

        for user in get_users(ticket).filtered(lambda u: u.login):
            email_vals = {
                'email_from': email_from,
                'email_to': user.login,
                'partner_ids': [(6, 0, [user.partner_id.id])],
            }
            ctx = {
                ctx_key: user,
                'lang': user.lang or self.env.user.lang,
            }
            template.with_context(**ctx).send_mail(
                ticket.id, force_send=True, email_values=email_vals
            )

    def _notify_users(self, template_field, get_users, ctx_key, sent_flag=None):
        email_from = self._get_email_from()
        tickets = sent_flag and self.filtered(lambda t: not getattr(t, sent_flag)) or self

        for ticket in tickets:
            self._send_for_ticket(ticket, template_field, get_users, ctx_key, email_from)
            if sent_flag:
                ticket.write({sent_flag: True})

    def _send_assignee_email_on_enter(self):
        return self._notify_users(
            'email_template_assignee_enter',
            lambda t: t.assigned_user_id,
            'assignee',
        )

    def _send_leader_email_on_enter(self):
        return self._notify_users(
            'email_template_leader_enter',
            lambda t: t.department_id.manager_id.user_id,
            'leader',
        )

    def _send_assignee_email_on_deadline(self):
        return self._notify_users(
            'email_template_assignee_deadline',
            lambda t: t.assigned_user_id,
            'assignee',
            sent_flag='email_assignee_sent',
        )

    def _send_leader_email_on_deadline(self):
        return self._notify_users(
            'email_template_leader_deadline',
            lambda t: t.department_id.manager_id.user_id,
            'leader',
            sent_flag='email_leader_sent',
        )

    def _send_reminder_notifications(self, users):
        template = self.env.ref(
            'dat_website_helpdesk.notification_template_ticket_reminder_overdue')
        notification_type = self.env.ref('dat_notification_management.notification_type_reminder')
        recipient_ids = [u.partner_id.id for u in users if notification_type in u.allowed_notification_type_ids]
        template.send_notification(
            res_ids=[self.id],
            recipient_ids=recipient_ids)

    def _send_assignee_noti_on_deadline(self):
        self.ensure_one()
        return self._send_reminder_notifications(self.assigned_user_id)

    def _send_leader_noti_on_deadline(self):
        self.ensure_one()
        return self._send_reminder_notifications(self.department_id.manager_id.user_id)

    @api.model
    def _cron_notify_before_deadline(self):
        now = fields.Datetime.now()
        for ticket, status in self._get_due_ticket_status_pairs(now):
            self._send_notifications(ticket, status)

    def _get_due_ticket_status_pairs(self, now):
        pairs = []
        tickets = self.search([
            ('step_id.notify_assignee_email_before_deadline', '=', True),
            ('deadline', '!=', False),
        ])
        for ticket in tickets:
            status = ticket.ticket_step_status_ids.filtered(lambda s: s.status == 'in_progress')
            if not status or status.deadline_notification_sent:
                continue

            user = status.assignee_ids and status.assignee_ids[0]
            if not user:
                continue
            calendar = user.resource_calendar_id or user.company_id.resource_calendar_id
            if not calendar:
                continue

            sla_hours = status.time_sla + status.hold_time
            lead_hours = ticket.step_id.notify_before_minutes / 60.0
            default_resource = self.env.ref("resource.resource_calendar_std")
            resource = (user.employee_ids.filtered(
                lambda e, ticket=ticket: e.company_id.id == ticket.branch.id
            ).resource_id) or default_resource
            notify_time = calendar.plan_hours(
                sla_hours - lead_hours,
                status.start_date,
                compute_leaves=True,
                resource=resource,
            )

            if now >= notify_time < ticket.deadline:
                pairs.append((ticket, status))
        return pairs

    def _send_notifications(self, ticket, status):
        if ticket.step_id.notify_assignee_email_before_deadline:
            ticket._send_assignee_email_on_deadline()
            ticket._send_assignee_noti_on_deadline()
            status.deadline_notification_sent = True
        if ticket.step_id.notify_leader_email_before_deadline:
            ticket._send_leader_email_on_deadline()
            ticket._send_leader_noti_on_deadline()
