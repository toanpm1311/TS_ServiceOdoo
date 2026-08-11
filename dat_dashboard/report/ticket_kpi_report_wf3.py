# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools
import logging

_logger = logging.getLogger(__name__)


class TicketKpiReport(models.Model):
    _name = 'ticket.kpi.report.wf3'
    _description = 'Ticket KPI Report Workflow 3'
    _auto = False

    user_id = fields.Many2one('res.users', 'User', readonly=True)
    create_date = fields.Date('Date', readonly=True)
    employee_id = fields.Many2one('hr.employee', 'Employee', readonly=True)
    department_id = fields.Many2one('hr.department', string='Department')
    company_id = fields.Many2one('res.company', 'Branch', readonly=True)
    ticket_id = fields.Many2one('ticket.helpdesk', 'Ticket', readonly=True)

    total_receiving_and_inspection_tasks = fields.Integer('Tổng số ticket phân công', readonly=True)
    total_receiving_and_inspection_time = fields.Float('Tổng thời gian phân công', readonly=True)
    total_receiving_and_inspection_sla_met = fields.Integer('Tổng số ticket phân công hoàn thành SLA', readonly=True)

    total_receiving_tasks = fields.Integer('Tổng số ticket tiếp nhận', readonly=True)
    total_receiving_time = fields.Float('Tổng thời gian tiếp nhận', readonly=True)
    total_receiving_sla_met = fields.Integer('Tổng số ticket tiếp nhận hoàn thành SLA', readonly=True)

    total_survey_tech_solutions_tasks = fields.Integer('Tổng số ticket khảo sát giải pháp', readonly=True)
    total_survey_tech_solutions_time = fields.Float('Tổng thời gian khảo sát giải pháp', readonly=True)
    total_survey_tech_solutions_sla_met = fields.Integer('Tổng số ticket khảo sát giải pháp hoàn thành SLA',
                                                         readonly=True)

    total_feedback_survey_results_tasks = fields.Integer('Tổng số ticket phản hồi khảo sát', readonly=True)
    total_feedback_survey_results_time = fields.Float('Tổng thời gian phản hồi khảo sát', readonly=True)
    total_feedback_survey_results_sla_met = fields.Integer('Tổng số ticket phản hồi khảo sát hoàn thành SLA',
                                                           readonly=True)

    total_approve_survey_results_tasks = fields.Integer('Tổng số ticket duyệt kết quả khảo sát', readonly=True)
    total_approve_survey_results_time = fields.Float('Tổng thời gian duyệt kết quả khảo sát', readonly=True)
    total_approve_survey_results_sla_met = fields.Integer('Tổng số ticket duyệt kết quả khảo sát hoàn thành SLA',
                                                          readonly=True)

    total_provide_tech_solutions_tasks = fields.Integer('Tổng số ticket cung cấp giải pháp', readonly=True)
    total_provide_tech_solutions_time = fields.Float('Tổng thời gian cung cấp giải pháp', readonly=True)
    total_provide_tech_solutions_sla_met = fields.Integer('Tổng số ticket cung cấp giải pháp hoàn thành SLA',
                                                          readonly=True)

    total_approve_tech_solution_tasks = fields.Integer('Tổng số ticket duyệt GPKT', readonly=True)
    total_approve_tech_solution_time = fields.Float('Tổng thời gian duyệt GPKT', readonly=True)
    total_approve_tech_solution_sla_met = fields.Integer('Tổng số ticket duyệt GPKT hoàn thành SLA',
                                                         readonly=True)

    total_prepare_quotation_tasks = fields.Integer('Tổng số ticket chuẩn bị báo giá', readonly=True)
    total_prepare_quotation_time = fields.Float('Tổng thời gian chuẩn bị báo giá', readonly=True)
    total_prepare_quotation_sla_met = fields.Integer('Tổng số ticket chuẩn bị báo giá hoàn thành SLA', readonly=True)

    total_provide_quotation_tasks = fields.Integer('Tổng số ticket cung cấp báo giá', readonly=True)
    total_provide_quotation_time = fields.Float('Tổng thời gian cung cấp báo giá', readonly=True)
    total_provide_quotation_sla_met = fields.Integer('Tổng số ticket cung cấp báo giá hoàn thành SLA', readonly=True)

    @api.model
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        step_map = {
            'receiving_and_inspection': 'dat_website_helpdesk.step_wf3_receiving_and_inspection',
            'receiving': 'dat_website_helpdesk.step_wf3_receiving',
            'survey_tech_solutions': 'dat_website_helpdesk.step_wf3_survey_tech_solutions',
            'feedback_survey_results': 'dat_website_helpdesk.step_wf3_feedback_survey_results',
            'approve_survey_results': 'dat_website_helpdesk.step_wf3_approve_survey_results',
            'provide_tech_solutions': 'dat_website_helpdesk.step_wf3_provide_tech_solutions',
            'approve_tech_solution': 'dat_website_helpdesk.step_wf3_approve_tech_solution',
            'prepare_quotation': 'dat_website_helpdesk.step_wf3_prepare_quotation',
            'provide_quotation': 'dat_website_helpdesk.step_wf3_provide_quotation',
        }

        step_ids = {
            key: self.env.ref(xmlid).id
            for key, xmlid in step_map.items()
        }
        rel_table = self.env['ticket.step.status']._fields['assignee_ids'].relation

        select_parts = []
        for key, sid in step_ids.items():
            select_parts.append(
                f"COUNT(DISTINCT CASE WHEN ts.step_id = {sid} THEN tk.id END)::integer AS total_{key}_tasks"
            )
            select_parts.append(
                f"SUM(CASE WHEN ts.step_id = {sid} THEN ts.time_spent ELSE 0 END)::float AS total_{key}_time"
            )
            select_parts.append(
                f"COUNT(DISTINCT CASE WHEN ts.step_id = {sid} AND ts.time_sla > 0 AND ts.time_spent < ts.time_sla THEN tk.id END)::integer AS total_{key}_sla_met"
            )

        select_sql = ",\n       ".join(select_parts)

        query = f"""
                CREATE VIEW {self._table} AS
                SELECT
                  ROW_NUMBER() OVER (ORDER BY tk.create_date::date, rel.res_users_id) AS id,
                  tk.create_date::date AS create_date,
                  tk.id       AS ticket_id,
                  rel.res_users_id       AS user_id,
                  he.id                  AS employee_id,
                  tk.department_id       AS department_id,
                  he.company_id          AS company_id,
                  {select_sql}
                FROM ticket_step_status ts
                JOIN {rel_table} rel ON rel.ticket_step_status_id = ts.id
                JOIN res_users ru     ON ru.id = rel.res_users_id
                LEFT JOIN hr_employee he ON he.user_id = ru.id
                LEFT JOIN ticket_helpdesk tk ON ts.ticket_id = tk.id AND ts.status IN ('done','reject')
                WHERE ts.step_id IN ({','.join(map(str, step_ids.values()))})
                  AND tk.active = TRUE
                GROUP BY
                  tk.create_date::date,
                  rel.res_users_id,
                  he.id,
                  tk.id,
                  tk.department_id,
                  he.company_id
                """

        self.env.cr.execute(query)
