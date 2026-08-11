# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools

class SurveyResearchTimeReport(models.Model):
    _name = 'survey.research.time.report'
    _description = 'Total Time Survey & Research Steps Report'
    _auto = False

    user_id           = fields.Many2one('res.users',   'User',       readonly=True)
    create_date       = fields.Date('Date', readonly=True)
    employee_id       = fields.Many2one('hr.employee', 'Employee',   readonly=True)
    department_name   = fields.Char('Department',      readonly=True)
    ticket_id         = fields.Many2one('ticket.helpdesk', 'Ticket', readonly=True)
    company_id        = fields.Many2one('res.company', 'Branch',     readonly=True)
    total_time_spent  = fields.Float('Total Time',      readonly=True)

    @api.model
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        step_ids = [
            self.env.ref('dat_website_helpdesk.step_wf3_receiving_and_inspection').id,
            self.env.ref('dat_website_helpdesk.step_wf3_survey_tech_solutions').id,
            self.env.ref('dat_website_helpdesk.step_wf3_feedback_survey_results').id,
            self.env.ref('dat_website_helpdesk.step_wf3_approve_survey_results').id,
        ]
        step_ids_str = ','.join(map(str, step_ids))
        rel_table = self.env['ticket.step.status']._fields['assignee_ids'].relation
        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS
            SELECT
                ROW_NUMBER() OVER (ORDER BY ts.create_date::date, ru.id, he.id, hd.name, ts.ticket_id, he.company_id) AS id,
                ts.create_date::date AS create_date,
                ru.id                                      AS user_id,
                he.id                                      AS employee_id,
                COALESCE(
                  hd.name->>'vi_VN',
                  hd.name->>'en_US'
                )                                           AS department_name,
                ts.ticket_id                               AS ticket_id,
                he.company_id                              AS company_id,
                SUM(ts.time_spent)::float                  AS total_time_spent
            FROM ticket_step_status ts
            JOIN {rel_table} rel
              ON rel.ticket_step_status_id = ts.id
            JOIN res_users ru
              ON ru.id = rel.res_users_id
            LEFT JOIN hr_employee he
              ON he.user_id = ru.id
            LEFT JOIN hr_department hd
              ON hd.id = he.department_id
            WHERE ts.step_id IN ({step_ids_str})
            GROUP BY ts.create_date::date, ru.id, he.id, hd.name, ts.ticket_id, he.company_id
        """)
