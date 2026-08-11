# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class StepProvideTechReport(models.Model):
    _name = 'step.provide.tech.report'
    _description = 'Provide Tech Solutions Step Report'
    _auto = False

    user_id = fields.Many2one('res.users', 'User', readonly=True)
    create_date = fields.Date('Date', readonly=True)
    employee_id = fields.Many2one('hr.employee', 'Employee', readonly=True)
    department_name = fields.Char('Department', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    step_count = fields.Integer('Count', readonly=True)

    @api.model
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        cr = self.env.cr
        step_id = self.env.ref('dat_website_helpdesk.step_wf3_provide_tech_solutions').id
        rel_table = self.env['ticket.step.status']._fields['assignee_ids'].relation
        cr.execute(f"""
                CREATE VIEW {self._table} AS
                SELECT
                    ROW_NUMBER() OVER (ORDER BY ts.create_date::date, ru.id, he.id, hd.name, he.company_id) AS id,
                    ts.create_date::date AS create_date,
                    ru.id                          AS user_id,
                    he.id                          AS employee_id,
                    COALESCE(
                        hd.name->>'vi_VN',
                        hd.name->>'en_US'
                    )                              AS department_name,
                    he.company_id                  AS company_id,
                    COUNT(ts.id)                   AS step_count
                FROM ticket_step_status ts
                JOIN {rel_table} rel
                  ON rel.ticket_step_status_id = ts.id
                JOIN res_users ru
                  ON ru.id = rel.res_users_id
                LEFT JOIN hr_employee he
                  ON he.user_id = ru.id
                LEFT JOIN hr_department hd
                  ON hd.id = he.department_id
                WHERE ts.step_id = {step_id}
                GROUP BY ts.create_date::date, ru.id, he.id, hd.name, he.company_id
            """)
