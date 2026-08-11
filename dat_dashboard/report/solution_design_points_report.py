# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools

class SolutionDesignPointsReport(models.Model):
    _name = 'solution.design.points.report'
    _description = 'Solution Design Points Report'
    _auto = False

    user_id         = fields.Many2one('res.users',   'User',      readonly=True)
    create_date = fields.Date('Date', readonly=True)
    employee_id     = fields.Many2one('hr.employee', 'Employee',  readonly=True)
    department_name = fields.Char(                  'Department',readonly=True)
    company_id      = fields.Many2one('res.company','Branch',    readonly=True)
    total_score     = fields.Float(                'Total Score',readonly=True)

    @api.model
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        cr        = self.env.cr

        rel_table = self.env['ticket.step.status']._fields['assignee_ids'].relation
        step_id   = self.env.ref('dat_website_helpdesk.step_wf3_provide_tech_solutions').id
        wf3_id    = self.env.ref('dat_website_helpdesk.workflow_3').id

        cr.execute(f"""
            CREATE VIEW {self._table} AS
            SELECT
              ROW_NUMBER() OVER (ORDER BY t.create_date::date, ru.id, he.id, hd.name, he.company_id) AS id,
              ru.id                                         AS user_id,
              t.create_date::date AS create_date,
              he.id                                         AS employee_id,
              COALESCE(
                hd.name->>'vi_VN',
                hd.name->>'en_US'
              )                                              AS department_name,
              he.company_id                                 AS company_id,
              -- Compute total_score based on evaluate_domain condition
              CASE 
                WHEN t.evaluate_domain = True THEN 
                    SUM(
                        (t.solution_total_point * 
                          (NULLIF(t.technical_solution_approval_multiplier, '')::float)
                        )
                        / NULLIF(parts.count, 0)
                    )::float
                ELSE 
                    SUM(
                        (t.installation_capacity * 
                          (NULLIF(t.technical_solution_approval_multiplier, '')::float)
                        )
                        / NULLIF(parts.count, 0)
                    )::float
              END AS total_score
            FROM ticket_helpdesk t
            /* count distinct participants on that step per ticket */
            JOIN LATERAL (
              SELECT COUNT(DISTINCT rel2.res_users_id) AS count
              FROM ticket_step_status sts2
              JOIN {rel_table} rel2
                ON rel2.ticket_step_status_id = sts2.id
              WHERE sts2.ticket_id = t.id
                AND sts2.step_id    = {step_id}
            ) parts ON TRUE
            /* join each assignment for that step */
            JOIN ticket_step_status sts
              ON sts.ticket_id = t.id
             AND sts.step_id   = {step_id}
            JOIN {rel_table} rel
              ON rel.ticket_step_status_id = sts.id
            JOIN res_users ru
              ON ru.id = rel.res_users_id
            LEFT JOIN hr_employee he
              ON he.user_id = ru.id
            LEFT JOIN hr_department hd
              ON hd.id = he.department_id
            WHERE t.workflow_id = {wf3_id}
            GROUP BY ru.id, t.create_date::date, he.id, hd.name, he.company_id, t.evaluate_domain
        """)
