# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class StepSlaComplianceReport(models.Model):
    _name = 'step.sla.compliance.report'
    _description = 'SLA Compliance Report'
    _auto = False

    ticket_id = fields.Many2one(
        'ticket.helpdesk', 'Ticket', readonly=True
    )
    create_date = fields.Date('Ticket Date', readonly=True)
    customer_id = fields.Many2one(
        'res.partner', 'Customer', readonly=True
    )
    request_type = fields.Many2one(
        'helpdesk.type', 'Request Type', readonly=True
    )
    priority_id = fields.Many2one(
        'ticket.priority', 'Priority', readonly=True
    )
    engineer_id = fields.Many2one(
        'res.users', 'Engineer', readonly=True
    )
    step_id = fields.Many2one(
        'ticket.step', 'Step Name', readonly=True
    )
    start_date = fields.Datetime('Step Start', readonly=True)
    end_date = fields.Datetime('Step End', readonly=True)
    time_sla = fields.Float('SLA (h)', readonly=True)
    time_spent = fields.Float('Actual (h)', readonly=True)
    difference = fields.Float('Difference (h)', readonly=True)
    sla_status = fields.Char('SLA Status', readonly=True)
    company_id = fields.Many2one(
        'res.company', 'Branch', readonly=True
    )

    @api.model
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        assignee_relation = (
            self.env['ticket.step.status']._fields['assignee_ids'].relation
        )

        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS
            SELECT
                ROW_NUMBER() OVER (
                    ORDER BY status.id, assignee.res_users_id
                ) AS id,
                status.ticket_id AS ticket_id,
                ticket.create_date::date AS create_date,
                ticket.customer_id AS customer_id,
                ticket.ticket_type_id AS request_type,
                ticket.priority_id AS priority_id,
                assignee.res_users_id AS engineer_id,
                status.step_id AS step_id,
                status.start_date AS start_date,
                status.end_date AS end_date,
                COALESCE(status.time_sla, 0.0)::float AS time_sla,
                COALESCE(status.time_spent, 0.0)::float AS time_spent,
                (
                    COALESCE(status.time_spent, 0.0)
                    - COALESCE(status.time_sla, 0.0)
                )::float AS difference,
                CASE
                    WHEN COALESCE(status.time_sla, 0.0) <= 0.0
                        THEN 'No SLA'
                    WHEN COALESCE(status.time_spent, 0.0) <= status.time_sla
                        THEN 'Met'
                    ELSE 'Exceeded'
                END AS sla_status,
                ticket.branch AS company_id
            FROM ticket_step_status status
            JOIN ticket_helpdesk ticket
              ON ticket.id = status.ticket_id
             AND ticket.active = TRUE
            LEFT JOIN {assignee_relation} assignee
              ON assignee.ticket_step_status_id = status.id
        """)
