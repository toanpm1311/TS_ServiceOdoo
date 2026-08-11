# -*- coding: utf-8 -*-
import io
import base64
from odoo import api, fields, models, _
from xlsxwriter import Workbook
from ..models.common_utils_mixin import CommonUtilsMixin
import logging

_logger = logging.getLogger(__name__)


class TicketKpiWF3WizardLine(models.TransientModel):
    _name = 'ticket.kpi.wf3.wizard.line'
    _description = 'Line for Ticket KPI WF3 Wizard'

    wizard_id = fields.Many2one('ticket.kpi.wf3.wizard', string='Wizard')
    stt = fields.Integer(string='STT')
    employee_name = fields.Char(string='Tên nhân viên')

    # --- Receiving & Inspection ---
    total_receiving_and_inspection_tasks = fields.Integer(
        string='Tổng số task phân công', readonly=True)
    total_receiving_and_inspection_time = fields.Float(
        string='Tổng thời gian phân công', readonly=True)
    avg_receiving_and_inspection_time = fields.Float(
        string='Thời gian trung bình bước phân công')
    receiving_and_inspection_on_time_rate_sla = fields.Float(
        string='Tỷ lệ hoàn thành đúng hạn bước phân công')
    total_receiving_and_inspection_sla_met = fields.Integer(
        string='Tổng số ticket phân công hoàn thành SLA', readonly=True)

    # --- Receiving ---
    total_receiving_tasks = fields.Integer(
        string='Tổng số task tiếp nhận', readonly=True)
    total_receiving_time = fields.Float(
        string='Tổng thời gian tiếp nhận', readonly=True)
    avg_receiving_time = fields.Float(
        string='Thời gian trung bình tiếp nhận')
    receiving_on_time_rate_sla = fields.Float(
        string='Tỷ lệ hoàn thành đúng hạn tiếp nhận')
    total_receiving_sla_met = fields.Integer(
        string='Tổng số ticket tiếp nhận hoàn thành SLA', readonly=True)

    # --- Survey Tech Solutions ---
    total_survey_tech_solutions_tasks = fields.Integer(
        string='Tổng số task khảo sát giải pháp', readonly=True)
    total_survey_tech_solutions_time = fields.Float(
        string='Tổng thời gian khảo sát giải pháp', readonly=True)
    avg_survey_tech_solutions_time = fields.Float(
        string='Thời gian trung bình khảo sát giải pháp')
    survey_tech_solutions_on_time_rate_sla = fields.Float(
        string='Tỷ lệ hoàn thành đúng hạn khảo sát giải pháp')
    total_survey_tech_solutions_sla_met = fields.Integer(
        string='Tổng số ticket khảo sát giải pháp hoàn thành SLA', readonly=True)

    # --- Feedback Survey Results ---
    total_feedback_survey_results_tasks = fields.Integer(
        string='Tổng số task phản hồi khảo sát', readonly=True)
    total_feedback_survey_results_time = fields.Float(
        string='Tổng thời gian phản hồi khảo sát', readonly=True)
    avg_feedback_survey_results_time = fields.Float(
        string='Thời gian trung bình phản hồi khảo sát')
    feedback_survey_results_on_time_rate_sla = fields.Float(
        string='Tỷ lệ hoàn thành đúng hạn phản hồi khảo sát')
    total_feedback_survey_results_sla_met = fields.Integer(
        string='Tổng số ticket phản hồi khảo sát hoàn thành SLA', readonly=True)

    # --- Approve Survey Results ---
    total_approve_survey_results_tasks = fields.Integer(
        string='Tổng số task duyệt kết quả khảo sát', readonly=True)
    total_approve_survey_results_time = fields.Float(
        string='Tổng thời gian duyệt kết quả khảo sát', readonly=True)
    avg_approve_survey_results_time = fields.Float(
        string='Thời gian trung bình duyệt kết quả khảo sát')
    approve_survey_results_on_time_rate_sla = fields.Float(
        string='Tỷ lệ hoàn thành đúng hạn duyệt kết quả khảo sát')
    total_approve_survey_results_sla_met = fields.Integer(
        string='Tổng số ticket duyệt kết quả khảo sát hoàn thành SLA', readonly=True)

    # --- Provide Tech Solutions ---
    total_provide_tech_solutions_tasks = fields.Integer(
        string='Tổng số task cung cấp giải pháp', readonly=True)
    total_provide_tech_solutions_time = fields.Float(
        string='Tổng thời gian cung cấp giải pháp', readonly=True)
    avg_provide_tech_solutions_time = fields.Float(
        string='Thời gian trung bình cung cấp giải pháp')
    provide_tech_solutions_on_time_rate_sla = fields.Float(
        string='Tỷ lệ hoàn thành đúng hạn cung cấp giải pháp')
    total_provide_tech_solutions_sla_met = fields.Integer(
        string='Tổng số ticket cung cấp giải pháp hoàn thành SLA', readonly=True)

    # --- Approve Tech Solution ---
    total_approve_tech_solution_tasks = fields.Integer(
        string='Tổng số task duyệt GPKT', readonly=True)
    total_approve_tech_solution_time = fields.Float(
        string='Tổng thời gian duyệt GPKT', readonly=True)
    avg_approve_tech_solution_time = fields.Float(
        string='Thời gian trung bình duyệt GPKT')
    approve_tech_solution_on_time_rate_sla = fields.Float(
        string='Tỷ lệ hoàn thành đúng hạn duyệt GPKT')
    total_approve_tech_solution_sla_met = fields.Integer(
        string='Tổng số ticket duyệt GPKT hoàn thành SLA', readonly=True)

    # --- Prepare Quotation ---
    total_prepare_quotation_tasks = fields.Integer(
        string='Tổng số task chuẩn bị báo giá', readonly=True)
    total_prepare_quotation_time = fields.Float(
        string='Tổng thời gian chuẩn bị báo giá', readonly=True)
    avg_prepare_quotation_time = fields.Float(
        string='Thời gian trung bình chuẩn bị báo giá')
    prepare_quotation_on_time_rate_sla = fields.Float(
        string='Tỷ lệ hoàn thành đúng hạn chuẩn bị báo giá')
    total_prepare_quotation_sla_met = fields.Integer(
        string='Tổng số ticket chuẩn bị báo giá hoàn thành SLA', readonly=True)

    # --- Provide Quotation ---
    total_provide_quotation_tasks = fields.Integer(
        string='Tổng số task cung cấp báo giá', readonly=True)
    total_provide_quotation_time = fields.Float(
        string='Tổng thời gian cung cấp báo giá', readonly=True)
    avg_provide_quotation_time = fields.Float(
        string='Thời gian trung bình cung cấp báo giá')
    provide_quotation_on_time_rate_sla = fields.Float(
        string='Tỷ lệ hoàn thành đúng hạn cung cấp báo giá')
    total_provide_quotation_sla_met = fields.Integer(
        string='Tổng số ticket cung cấp báo giá hoàn thành SLA', readonly=True)

    total_design_score = fields.Char(string='Tổng điểm thiết kế GPKT')
    total_design_sale_score = fields.Char(string='Tổng điểm chốt sale thiết kế GPKT')
    design_sale_score_ratio = fields.Char(string='Tỷ lệ điểm chốt sale')


class TicketKpiWF3Wizard(models.TransientModel, CommonUtilsMixin):
    _name = 'ticket.kpi.wf3.wizard'
    _description = 'Ticket KPI Workflow 3 Report Wizard'

    department_name = fields.Many2one('hr.department', string='Department')
    date_from = fields.Date(string='Ticket Date From')
    date_to = fields.Date(string='Ticket Date To')
    total_survey_tech_solutions_tasks = fields.Integer(
        string='Tổng số task tư vấn/khảo sát',
        compute='_compute_dashboard_stats',
        readonly=True)
    average_assignment_acceptance_time = fields.Float(string='Thời gian trung bình phân công và tiếp nhận',
                                                      readonly=True)
    on_time_assignment_acceptance_rate = fields.Float(string='Tỷ lệ hoàn thành đúng hạn phân công và tiếp nhận SLA',
                                                      readonly=True)
    total_technical_support_time = fields.Float(string='Tổng thời gian hỗ trợ kỹ thuật', readonly=True)
    average_technical_support_time = fields.Float(string='Thời gian trung bình hỗ trợ kỹ thuật', readonly=True)
    on_time_technical_support_rate = fields.Float(string='Tỷ lệ hoàn thành đúng hạn hỗ trợ kỹ thuật SLA', readonly=True)
    total_feasible_design_tasks = fields.Integer(string='Tổng số task thiết kế cung cấp GPKT khả thi', readonly=True)
    average_feasible_design_time = fields.Float(string='Thời gian trung bình của thiết kế cung cấp GPKT khả thi',
                                                readonly=True)
    total_feasible_design_score = fields.Integer(string='Tổng điểm thiết kế GPKT', readonly=True)
    total_closed_sale_design_score = fields.Integer(string='Tổng điểm chốt sale thiết kế GPKT', readonly=True)
    closed_sale_score_rate = fields.Float(string='Tỷ lệ điểm chốt sale', readonly=True)
    on_time_feasible_design_rate = fields.Float(string='Tỷ lệ hoàn thành đúng hạn cung cấp GPKT khả thi SLA',
                                                readonly=True)
    average_quotation_creation_time = fields.Float(string='Thời gian trung bình của lập báo giá', readonly=True)
    on_time_quotation_creation_rate = fields.Float(string='Tỷ lệ hoàn thành đúng hạn lập báo giá SLA', readonly=True)
    average_customer_quotation_design_time = fields.Float(string='Thời gian trung bình thiết kế báo giá khách hàng',
                                                          readonly=True)
    total_closed_sale_design_tasks = fields.Integer(string='Tổng số task thiết kế chốt sale', readonly=True)
    closed_sale_design_task_rate = fields.Float(string='Tỷ lệ task thiết kế chốt sale', readonly=True)
    on_time_customer_quotation_rate = fields.Float(string='Tỷ lệ hoàn thành đúng hạn báo giá khách hàng', readonly=True)

    line_ids = fields.One2many(
        'ticket.kpi.wf3.wizard.line',
        'wizard_id',
        compute='_compute_lines',
        store=True,
        readonly=True,
    )

    @api.depends('department_name', 'date_from', 'date_to')
    def _compute_lines(self):
        for wiz in self:
            wiz.line_ids = [(5, 0, 0)]
            dom = []
            if wiz.department_name: dom.append(('department_name', 'ilike', wiz.department_name.name))
            if wiz.department_name.company_id.id: dom.append(('company_id', '=', wiz.department_name.company_id.id))
            if wiz.date_from: dom.append(('start_date', '>=', wiz.date_from))
            if wiz.date_to: dom.append(('end_date', '<=', wiz.date_to))
            group_fields = [
                'user_id', 'employee_id', 'department_id', 'company_id'
            ]

            recs = self.env['ticket.kpi.report.wf3'].read_group(
                domain=dom,
                fields=[
                    # Receiving & Inspection
                    'total_receiving_and_inspection_tasks',
                    'total_receiving_and_inspection_time',
                    'total_receiving_and_inspection_sla_met',
                    # Receiving
                    'total_receiving_tasks',
                    'total_receiving_time',
                    'total_receiving_sla_met',
                    # Survey Tech Solutions
                    'total_survey_tech_solutions_tasks',
                    'total_survey_tech_solutions_time',
                    'total_survey_tech_solutions_sla_met',
                    # Feedback Survey Results
                    'total_feedback_survey_results_tasks',
                    'total_feedback_survey_results_time',
                    'total_feedback_survey_results_sla_met',
                    # Approve Survey Results
                    'total_approve_survey_results_tasks',
                    'total_approve_survey_results_time',
                    'total_approve_survey_results_sla_met',
                    # Provide Tech Solutions
                    'total_provide_tech_solutions_tasks',
                    'total_provide_tech_solutions_time',
                    'total_provide_tech_solutions_sla_met',
                    # Approve Tech Solution
                    'total_approve_tech_solution_tasks',
                    'total_approve_tech_solution_time',
                    'total_approve_tech_solution_sla_met',
                    # Prepare Quotation
                    'total_prepare_quotation_tasks',
                    'total_prepare_quotation_time',
                    'total_prepare_quotation_sla_met',
                    # Provide Quotation
                    'total_provide_quotation_tasks',
                    'total_provide_quotation_time',
                    'total_provide_quotation_sla_met',
                    # Grouping keys
                    'user_id', 'employee_id', 'department_id', 'company_id',
                ],
                groupby=group_fields,
                orderby='user_id',
                lazy=False,
            )
            lines = []
            for idx, rec in enumerate(recs, start=1):
                def safe_avg(time_key, count_key):
                    cnt = rec.get(count_key) or 0
                    return (rec.get(time_key) or 0) / cnt if cnt else 0

                def safe_rate(sla_key, count_key):
                    cnt = rec.get(count_key) or 0
                    return (rec.get(sla_key) or 0) / cnt if cnt else 0

                lines.append((0, 0, {
                    'stt': idx,
                    'employee_name': rec.get('employee_id')[1] if rec.get('employee_id') else '',
                    # --- Receiving & Inspection ---
                    'total_receiving_and_inspection_tasks': rec.get('total_receiving_and_inspection_tasks') or 0,
                    'total_receiving_and_inspection_time': rec.get('total_receiving_and_inspection_time') or 0,
                    'total_receiving_and_inspection_sla_met': rec.get('total_receiving_and_inspection_sla_met') or 0,
                    'avg_receiving_and_inspection_time': safe_avg('total_receiving_and_inspection_time',
                                                                  'total_receiving_and_inspection_tasks'),
                    'receiving_and_inspection_on_time_rate_sla': safe_rate('total_receiving_and_inspection_sla_met',
                                                                           'total_receiving_and_inspection_tasks'),
                    # --- Receiving ---
                    'total_receiving_tasks': rec.get('total_receiving_tasks') or 0,
                    'total_receiving_time': rec.get('total_receiving_time') or 0,
                    'total_receiving_sla_met': rec.get('total_receiving_sla_met') or 0,
                    'avg_receiving_time': safe_avg('total_receiving_time', 'total_receiving_tasks'),
                    'receiving_on_time_rate_sla': safe_rate('total_receiving_sla_met', 'total_receiving_tasks'),
                    # --- Survey Tech Solutions ---
                    'total_survey_tech_solutions_tasks': rec.get('total_survey_tech_solutions_tasks') or 0,
                    'total_survey_tech_solutions_time': rec.get('total_survey_tech_solutions_time') or 0,
                    'total_survey_tech_solutions_sla_met': rec.get('total_survey_tech_solutions_sla_met') or 0,
                    'avg_survey_tech_solutions_time': safe_avg('total_survey_tech_solutions_time',
                                                               'total_survey_tech_solutions_tasks'),
                    'survey_tech_solutions_on_time_rate_sla': safe_rate('total_survey_tech_solutions_sla_met',
                                                                        'total_survey_tech_solutions_tasks'),
                    # --- Feedback Survey Results ---
                    'total_feedback_survey_results_tasks': rec.get('total_feedback_survey_results_tasks') or 0,
                    'total_feedback_survey_results_time': rec.get('total_feedback_survey_results_time') or 0,
                    'total_feedback_survey_results_sla_met': rec.get('total_feedback_survey_results_sla_met') or 0,
                    'avg_feedback_survey_results_time': safe_avg('total_feedback_survey_results_time',
                                                                 'total_feedback_survey_results_tasks'),
                    'feedback_survey_results_on_time_rate_sla': safe_rate('total_feedback_survey_results_sla_met',
                                                                          'total_feedback_survey_results_tasks'),
                    # --- Approve Survey Results ---
                    'total_approve_survey_results_tasks': rec.get('total_approve_survey_results_tasks') or 0,
                    'total_approve_survey_results_time': rec.get('total_approve_survey_results_time') or 0,
                    'total_approve_survey_results_sla_met': rec.get('total_approve_survey_results_sla_met') or 0,
                    'avg_approve_survey_results_time': safe_avg('total_approve_survey_results_time',
                                                                'total_approve_survey_results_tasks'),
                    'approve_survey_results_on_time_rate_sla': safe_rate('total_approve_survey_results_sla_met',
                                                                         'total_approve_survey_results_tasks'),
                    # --- Provide Tech Solutions ---
                    'total_provide_tech_solutions_tasks': rec.get('total_provide_tech_solutions_tasks') or 0,
                    'total_provide_tech_solutions_time': rec.get('total_provide_tech_solutions_time') or 0,
                    'total_provide_tech_solutions_sla_met': rec.get('total_provide_tech_solutions_sla_met') or 0,
                    'avg_provide_tech_solutions_time': safe_avg('total_provide_tech_solutions_time',
                                                                'total_provide_tech_solutions_tasks'),
                    'provide_tech_solutions_on_time_rate_sla': safe_rate('total_provide_tech_solutions_sla_met',
                                                                         'total_provide_tech_solutions_tasks'),
                    # --- Approve Tech Solution ---
                    'total_approve_tech_solution_tasks': rec.get('total_approve_tech_solution_tasks') or 0,
                    'total_approve_tech_solution_time': rec.get('total_approve_tech_solution_time') or 0,
                    'total_approve_tech_solution_sla_met': rec.get('total_approve_tech_solution_sla_met') or 0,
                    'avg_approve_tech_solution_time': safe_avg('total_approve_tech_solution_time',
                                                               'total_approve_tech_solution_tasks'),
                    'approve_tech_solution_on_time_rate_sla': safe_rate('total_approve_tech_solution_sla_met',
                                                                        'total_approve_tech_solution_tasks'),
                    # --- Prepare Quotation ---
                    'total_prepare_quotation_tasks': rec.get('total_prepare_quotation_tasks') or 0,
                    'total_prepare_quotation_time': rec.get('total_prepare_quotation_time') or 0,
                    'total_prepare_quotation_sla_met': rec.get('total_prepare_quotation_sla_met') or 0,
                    'avg_prepare_quotation_time': safe_avg('total_prepare_quotation_time',
                                                           'total_prepare_quotation_tasks'),
                    'prepare_quotation_on_time_rate_sla': safe_rate('total_prepare_quotation_sla_met',
                                                                    'total_prepare_quotation_tasks'),
                    # --- Provide Quotation ---
                    'total_provide_quotation_tasks': rec.get('total_provide_quotation_tasks') or 0,
                    'total_provide_quotation_time': rec.get('total_provide_quotation_time') or 0,
                    'total_provide_quotation_sla_met': rec.get('total_provide_quotation_sla_met') or 0,
                    'avg_provide_quotation_time': safe_avg('total_provide_quotation_time',
                                                           'total_provide_quotation_tasks'),
                    'provide_quotation_on_time_rate_sla': safe_rate('total_provide_quotation_sla_met',
                                                                    'total_provide_quotation_tasks'),
                }))
            wiz.line_ids = lines

    @api.depends('line_ids.total_survey_tech_solutions_tasks')
    def _compute_dashboard_stats(self):
        for rec in self:
            lines = rec.line_ids
            # Tổng số task khảo sát
            rec.total_survey_tech_solutions_tasks = sum(line.total_survey_tech_solutions_tasks for line in lines)

    def action_reset_view(self):
        self.ensure_one()
        return self.env.ref('dat_dashboard.action_ticket_kpi_wf3_wizard').read()[0]

    def action_export_xlsx(self):
        self.ensure_one()

        output = io.BytesIO()
        wb = Workbook(output, {'in_memory': True})
        sheet = wb.add_worksheet(_('KPI'))
        sheet.set_column('A:A', 40)
        sheet.set_column('B:B', 25)
        sheet.set_column(4, 27, 30)
        filter_data = [
            (_('QUY TRÌNH CUNG CẤP GPKT'), ''),
            (_('Department'), ', '.join(self.mapped('department_name.name'))),
            (_('Ticket Date From'),
             ', '.join([rec.date_from.strftime('%d/%m/%Y') if rec.date_from else '' for rec in self])),
            (_('Ticket Date To'), ', '.join([rec.date_to.strftime('%d/%m/%Y') if rec.date_to else '' for rec in self])),
            (_('Tổng số task tư vấn/khảo sát'), sum(rec.total_survey_tech_solutions_tasks for rec in self.line_ids)),
            (_('Thời gian trung bình phân công và tiếp nhận'), 3.9),
            (_('Tỷ lệ hoàn thành đúng hạn phân công và tiếp nhận SLA'), 416.5),
            (_('Tổng thời gian hỗ trợ kỹ thuật'), 25689),
            (_('Thời gian trung bình hỗ trợ kỹ thuật'), 9051),
            (_('Tỷ lệ hoàn thành đúng hạn hỗ trợ kỹ thuật SLA'), '35%'),
            (_('Tổng số task thiết kế cung cấp GPKT khả thi'), '100%'),
            (_('Tổng điểm thiết kế GPKT'), '100%'),
            (_('Tổng điểm chốt sale thiết kế GPKT'), '100%'),
            (_('Tỷ lệ điểm chốt sale'), '100%'),
            (_('Tỷ lệ hoàn thành đúng hạn cung cấp GPKT khả thi SLA'), '100%'),
            (_('Thời gian trung bình của lập báo giá'), '100%'),
            (_('Tỷ lệ hoàn thành đúng hạn lập báo giá SLA'), '100%'),
            (_('Thời gian trung bình thiết kế báo giá khách hàng'), '100%'),
            (_('Tổng số task thiết kế chốt sale'), '100%'),
            (_('Tỷ lệ hoàn thành đúng hạn báo giá khách hàng'), '100%'),
        ]
        for row_num, (label, value) in enumerate(filter_data):
            sheet.write(row_num, 0, label)
            sheet.write(row_num, 1, value)

        # Ghi bảng dữ liệu chi tiết
        headers = [
            _('STT'),
            _('Tên nhân viên'),
            _('Tổng số task tư vấn/khảo sát'),
            _('Thời gian trung bình tiếp nhận và phân công'),
            _('Tỷ lệ hoàn thành đúng hạn bước phân công (leader) SLA'),
            _('Thời gian trung bình tiếp nhận yêu cầu (nhân viên)'),
            _('Tỷ lệ hoàn thành đúng hạn tiếp nhận yêu cầu (nhân viên) SLA'),
            _('Tổng thời gian tư vấn/khảo sát và phản hồi kết quả'),
            _('Thời gian trung bình tư vấn/khảo sát và phản hồi kết quả'),
            _('Thời gian trung bình duyệt kết quả'),
            _('Tổng số tasks thiết kế cung cấp GPKT khả thi'),
            _('Tổng thời gian thiết kế cung cấp GPKT khả thi'),
            _('Thời gian trung bình của thiết kế cung cấp GPKT khả thi'),
            _('Tổng điểm thiết kế GPKT'),
            _('Tổng điểm chốt sale thiết kế GPKT'),
            _('Tỷ lệ điểm chốt sale'),
            _('Tỷ lệ hoàn thành đúng hạn cung cấp GPKT khả thi SLA'),
            _('Tỷ lệ task thiết kế chốt sale'),
            _('Thời gian trung bình duyệt thiết kế GPKT khả thi'),
            _('Tổng thời gian lập báo giá'),
            _('Tỷ lệ hoàn thành đúng hạn lập báo giá SLA'),
            _('Tổng thời gian báo giá khách hàng'),
            _('Thời gian trung bình báo giá khách hàng'),
            _('Tổng số task thiết kế chốt sale')
        ]
        start_col = 3
        start_row = 0
        for c, h in enumerate(headers):
            sheet.write(start_row, start_col + c, h)

        for r, rec in enumerate(self.line_ids, start=1):
            total_time_spent_label = self.float_to_time_string(float(rec.total_survey_tech_solutions_tasks))
            row = [
                rec.stt or '',
                rec.employee_name or '',
                rec.total_survey_tech_solutions_tasks or '',
                rec.avg_assignment_acceptance_time or '',
                rec.assignment_on_time_rate_sla or '',
                rec.avg_receiving_and_inspection_time or '',
                rec.receiving_and_inspection_on_time_rate_sla or '',
                rec.total_survey_and_response_time or '',
                rec.avg_survey_time or '',
                rec.avg_result_approval_time or '',
                rec.total_feasible_design_tasks or '',
                rec.total_feasible_design_time or '',
                rec.avg_feasible_design_time or '',
                rec.total_design_score or '',
                rec.total_design_sale_score or '',
                rec.design_sale_score_ratio or '',
                rec.design_on_time_rate_sla or '',
                rec.design_to_sale_task_ratio or '',
                rec.avg_feasible_design_approval_time or '',
                rec.total_quote_preparation_time or '',
                rec.quote_on_time_rate_sla or '',
                rec.total_customer_quote_time or '',
                rec.avg_customer_quote_time or '',
                rec.total_design_sale_tasks or '',
            ]
            for c, val in enumerate(row):
                sheet.write(start_row + r, start_col + c, val)

        wb.close()
        data = output.getvalue()
        fname = _('KPI_Report.xlsx')
        attachment = self.env['ir.attachment'].create({
            'name': fname,
            'datas': base64.b64encode(data),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true&filename={fname}',
            'target': 'new',
        }
