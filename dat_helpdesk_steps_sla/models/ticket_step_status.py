import math
from odoo import fields, models, api, _


class TicketStepStatus(models.Model):
    _name = 'ticket.step.status'
    _description = 'Ticket Step Status'

    step_id = fields.Many2one('ticket.step', string='Step')
    step_name = fields.Char(related='step_id.name', string='Step Name')
    assignee_ids = fields.Many2many('res.users', string='Assignees')
    start_date = fields.Datetime(string='Start Date', default=fields.Datetime.now)
    deadline = fields.Datetime(string='Deadline')
    status = fields.Selection([('not_started', 'Not Started'), ('in_progress', 'In Progress'), ('on_hold', 'On Hold'), ('done', 'Done'), ('rejected', 'Rejected')],
                              compute='_compute_status', default='not_started', string='Status', store=True)
    ticket_id = fields.Many2one('ticket.helpdesk', string='Ticket')
    hold_date = fields.Datetime(string='Hold Date')
    hold_time = fields.Float(string='Hold Time')
    time_spent = fields.Float(string='Time Spent', compute='_compute_time_spent', store=True)
    end_date = fields.Datetime(string='End Date', compute='_compute_time_spent', store=True)
    time_alert = fields.Datetime(string='Time Alert')
    time_check = fields.Datetime(string='Time Check', compute='_compute_current_time_spent', readonly=False)
    time_sla = fields.Float(string='SLA Time')
    deadline_notification_sent = fields.Boolean(
        string='Deadline already notified?',
        default=False
    )

    def action_compute_deadline(self):
        for status in self:
            assignee_id = status.assignee_ids[0] if status.assignee_ids else self.env['res.users']
            if not status.step_id or status.step_id.step_sla_hours == 0:
                continue

            deadline = status.start_date
            working_calendar = assignee_id.resource_calendar_id or assignee_id.company_id.resource_calendar_id
            if not working_calendar:
                status.deadline = deadline
                continue
            default_resource = self.env.ref("resource.resource_calendar_std")
            resource_id = assignee_id.employee_ids.filtered(lambda x: x.company_id.id == status.ticket_id.branch.id).resource_id or default_resource

            sla_times = status.step_id.step_sla_hours * status.ticket_id.priority_id.percentage_hours / 100
            percent_warning = self.step_id.workflow_id.percent_warning
            if percent_warning == 0:
                percent_warning = 1
            alert_times = sla_times * percent_warning
            status.time_sla = sla_times
            sla_times += status.hold_time
            alert_times += status.hold_time
            status.deadline = deadline and working_calendar.plan_hours(sla_times, deadline, compute_leaves=True, resource=resource_id)
            status.time_alert = deadline and working_calendar.plan_hours(alert_times, deadline, compute_leaves=True, resource=resource_id)

    @api.depends('status', 'start_date')
    def _compute_time_spent(self):
        for status in self:
            if status.status == 'done' and not status.time_spent:
                assignee_ids = status.assignee_ids
                end_date = fields.Datetime.now()
                time_spent = (end_date - status.start_date).total_seconds() / 3600
                if assignee_ids:
                    working_calendar = assignee_ids[0].resource_calendar_id or assignee_ids[0].company_id.resource_calendar_id
                    if working_calendar:
                        resource_id = assignee_ids[0].employee_ids.filtered(lambda x: x.company_id.id == status.ticket_id.branch.id).resource_id
                        time_spent = working_calendar.get_work_duration_data_with_resource(status.start_date, end_date, compute_leaves=True, resource=resource_id)['hours']
                status.time_spent = time_spent
                status.end_date = end_date

    @api.depends('ticket_id.step_id')
    def _compute_current_time_spent(self):
        for status in self:
            if status.status == 'in_progress':
                status.time_check = fields.Datetime.now()

    @api.depends('ticket_id.child_ids.status')
    def _compute_status(self):
        for status in self:
            if status.ticket_id.status not in ('rejected','done') and status.ticket_id.child_ids and all(status == "closed" for status in status.ticket_id.child_ids.mapped('status')):
                status.status = 'done'
            else:
                status.status = status.status
