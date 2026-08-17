# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools

class StepSlaComplianceReport(models.Model):
    _name = 'step.sla.compliance.report'
    _description = 'SLA Compliance Detail Report'
    _auto = False

    ticket_id = fields.Many2one('ticket.helpdesk', 'Ticket', readonly=True)
    create_date = fields.Date('Ticket Date', readonly=True)
    customer_id = fields.Many2one('res.partner', 'Customer', readonly=True)
    request_type = fields.Many2one('helpdesk.type', 'Request Type', readonly=True)
    priority_id = fields.Many2one('ticket.priority', 'Priority', readonly=True)
    engineer_id = fields.Many2one('res.users', 'Engineer', readonly=True)
    step_id = fields.Many2one('ticket.step', 'Step Name', readonly=True)
    start_date = fields.Datetime('Step Start', readonly=True)
    end_date = fields.Datetime('Step End', readonly=True)
    time_sla = fields.Float('SLA (h)', readonly=True)
    time_spent = fields.Float('Actual (h)', readonly=True)
    difference = fields.Float('Difference (h)', readonly=True)
    sla_status = fields.Char('SLA Status', readonly=True)
    company_id = fields.Many2one('res.company', 'Branch', readonly=True)

    @api.model
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        cr = self.env.cr
        rel_table = self.env['ticket.step.status']._fields['assignee_ids'].relation

        cr.execute(f"""
            CREATE VIEW {self._table} AS
            SELECT
              ROW_NUMBER() OVER (ORDER BY t.create_date::date, t.id, t.branch, t.customer_id, t.ticket_type_id, t.priority_id, ru.id, sts.step_id, sts.start_date, sts.end_date) AS id,
              t.id                                                       AS ticket_id,
              t.create_date::date                                        AS create_date,
              t.branch                                                   AS company_id,
              t.customer_id                                              AS customer_id,
              t.ticket_type_id                                           AS request_type,
              t.priority_id                                              AS priority_id,
              ru.id                                                      AS engineer_id,
              sts.step_id                                                AS step_id,
              sts.start_date                                             AS start_date,
              sts.end_date                                               AS end_date,
              sts.time_sla                                               AS time_sla,
              sts.time_spent                                             AS time_spent,
              (sts.time_sla - sts.time_spent)::float                     AS difference,
              CASE
                WHEN sts.time_sla IS NOT NULL
                     AND sts.time_spent <= sts.time_sla THEN 'On Time'
                ELSE 'Overdue'
              END                                                         AS sla_status
            FROM ticket_step_status sts
            JOIN {rel_table} rel
              ON rel.ticket_step_status_id = sts.id
            JOIN res_users ru
              ON ru.id = rel.res_users_id
            JOIN ticket_helpdesk t
              ON t.id = sts.ticket_id
            WHERE sts.time_sla IS NOT NULL
        """)
