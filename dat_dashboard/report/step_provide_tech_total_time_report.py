# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class StepProvideTotalTimeReport(models.Model):
    _name = 'step.provide.total.time.report'
    _description = 'Total Time Spent on Provide & Approve Steps'
    _auto = False

    create_date = fields.Date(string='Create Date', readonly=True)
    department_id = fields.Many2one(
        'hr.department', 'Department', readonly=True
    )
    company_id = fields.Many2one(
        'res.company', 'Branch', readonly=True
    )
    employee_id = fields.Many2one(
        'hr.employee', 'Employee', readonly=True
    )
    total_time_spent = fields.Float(
        'Total Time Spent (h)', digits=(16, 2), readonly=True
    )

    @api.model
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        cr = self.env.cr

        rel_table = self.env['ticket.step.status']._fields['assignee_ids'].relation

        step_ids = [
            self.env.ref('dat_website_helpdesk.step_wf3_provide_tech_solutions').id,
            self.env.ref('dat_website_helpdesk.step_wf3_approve_tech_solution').id,
        ]
        step_ids_str = ','.join(map(str, step_ids))

        cr.execute(f"""
            CREATE VIEW {self._table} AS
            SELECT
              ROW_NUMBER() OVER (ORDER BY sts.create_date::date, he.department_id, t.branch, he.id) AS id,
              sts.create_date::date AS create_date,
              he.department_id       AS department_id,
              t.branch               AS company_id,
              he.id                  AS employee_id,
              SUM(sts.time_spent)    AS total_time_spent
            FROM ticket_step_status sts
            JOIN ticket_helpdesk t
              ON sts.ticket_id = t.id
             AND t.active = TRUE
            JOIN {rel_table} rel
              ON rel.ticket_step_status_id = sts.id
            JOIN res_users ru
              ON ru.id = rel.res_users_id
            LEFT JOIN hr_employee he
              ON he.user_id = ru.id
            WHERE sts.step_id IN ({step_ids_str})
            GROUP BY sts.create_date::date, he.department_id, t.branch, he.id
        """)
