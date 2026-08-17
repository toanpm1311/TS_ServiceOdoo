import logging
from datetime import date, datetime
from ..fields.custom_float import CustomFloat
import json              
import requests  

import pytz
from odoo import _, api, fields, models
from odoo.addons.dat_website_helpdesk.tools.validate_phone import is_valid_phone_number
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

RATING = [
    ('0', 'Very Low'),
    ('1', 'Low'),
    ('2', 'Normal'),
    ('3', 'High'),
    ('4', 'Very High'),
    ('5', 'Extreme High')
]

HR_DEPARTMENT_MODEL = 'hr.department'
EXCLUDED_SAP_REASON_CODES = ("04-994", "04-995")


class TicketHelpDesk(models.Model):
    _name = 'ticket.helpdesk'
    _description = 'Helpdesk Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'abstract.uuid']
    _order = 'priority_id desc, create_date desc, name desc'

    # =====================================================
    # WORKFLOWS (XMLIDs)
    # =====================================================
    WORKFLOW_1 = 'dat_website_helpdesk.workflow_1'  # Warranty/Repair at DAT + dispatch material + (optional) onsite
    WORKFLOW_2 = 'dat_website_helpdesk.workflow_2'  # Onsite/Online support flow
    WORKFLOW_3 = 'dat_website_helpdesk.workflow_3'  # Survey/Quotation flow
    WORKFLOW_4 = 'dat_website_helpdesk.workflow_4'  # Deployment/Acceptance flow
    WORKFLOW_RETURN = 'dat_website_helpdesk.workflow_return'

    # =====================================================
    # TICKET TYPES (XMLIDs) - Keep for backward compatibility
    # NOTE: khuyến nghị về lâu dài dùng field code/selection thay vì type_1..4
    # =====================================================
    TICKET_TYPE_1 = 'dat_website_helpdesk.ticket_type_1'
    TICKET_TYPE_2 = 'dat_website_helpdesk.ticket_type_2'
    TICKET_TYPE_3 = 'dat_website_helpdesk.ticket_type_3'
    TICKET_TYPE_4 = 'dat_website_helpdesk.ticket_type_4'
    TICKET_TYPE_RETURN = 'dat_website_helpdesk.ticket_type_return'

    # Product return workflow steps
    WORKFLOW_RETURN_STEP_ASSIGN = 'dat_website_helpdesk.step_return_assign'
    WORKFLOW_RETURN_STEP_COMPLETE = 'dat_website_helpdesk.step_return_complete'

    # =====================================================
    # WF1 STEPS (XMLIDs) - existing
    # =====================================================
    WORKFLOW_1_STEP_2  = 'dat_website_helpdesk.step_wf1_receiving_and_inspection'
    WORKFLOW_1_STEP_2b = 'dat_website_helpdesk.step_wf1_receiving'
    WORKFLOW_1_STEP_3  = 'dat_website_helpdesk.step_wf1_repair_quotation'
    WORKFLOW_1_STEP_4  = 'dat_website_helpdesk.step_wf1_material_dispatch'
    WORKFLOW_1_STEP_5  = 'dat_website_helpdesk.step_wf1_repair'
    WORKFLOW_1_STEP_6  = 'dat_website_helpdesk.step_wf1_reassembly_to_original_state'
    WORKFLOW_1_STEP_7  = 'dat_website_helpdesk.step_wf1_product_delivery'
    WORKFLOW_1_STEP_8  = 'dat_website_helpdesk.step_wf1_on_site_installation_and_repair'

    # =====================================================
    # WF1 STEPS (XMLIDs) - NEW (tối ưu theo quy trình)
    # =====================================================
    # Step dùng cho nhánh "BH 1 đổi 1": bắt cập nhật Replace Serial / xác nhận nhận hàng lỗi
    WORKFLOW_1_STEP_5A = 'dat_website_helpdesk.step_wf1_confirm_replace_and_serial'

    # Step chốt kỹ thuật: xác nhận giao trả & đóng ticket (Technical Done)
    WORKFLOW_1_STEP_9  = 'dat_website_helpdesk.step_wf1_technical_done_close'

    # =====================================================
    # WF2 STEPS (XMLIDs)
    # =====================================================
    WORKFLOW_2_STEP_2  = 'dat_website_helpdesk.step_wf2_receiving_and_inspection'
    WORKFLOW_2_STEP_2b = 'dat_website_helpdesk.step_wf2_receiving'
    WORKFLOW_2_STEP_3  = 'dat_website_helpdesk.step_wf2_go_to_location'
    WORKFLOW_2_STEP_4  = 'dat_website_helpdesk.step_wf2_begin_processing'
    WORKFLOW_2_STEP_5  = 'dat_website_helpdesk.step_wf2_installation_completed'
    WORKFLOW_2_STEP_6  = 'dat_website_helpdesk.step_wf2_approval'  # existing approval/acceptance step

    # =====================================================
    # WF3 STEPS (XMLIDs)
    # =====================================================
    WORKFLOW_3_STEP_2  = 'dat_website_helpdesk.step_wf3_receiving_and_inspection'
    WORKFLOW_3_STEP_2b = 'dat_website_helpdesk.step_wf3_receiving'
    WORKFLOW_3_STEP_3  = 'dat_website_helpdesk.step_wf3_survey_tech_solutions'
    WORKFLOW_3_STEP_4  = 'dat_website_helpdesk.step_wf3_feedback_survey_results'
    WORKFLOW_3_STEP_5  = 'dat_website_helpdesk.step_wf3_approve_survey_results'
    WORKFLOW_3_STEP_6  = 'dat_website_helpdesk.step_wf3_provide_tech_solutions'
    WORKFLOW_3_STEP_7  = 'dat_website_helpdesk.step_wf3_approve_tech_solution'
    WORKFLOW_3_STEP_8  = 'dat_website_helpdesk.step_wf3_prepare_quotation'
    WORKFLOW_3_STEP_9  = 'dat_website_helpdesk.step_wf3_provide_quotation'

    # =====================================================
    # WF4 STEPS (XMLIDs)
    # =====================================================
    WORKFLOW_4_STEP_2          = 'dat_website_helpdesk.step_wf4_receiving_and_inspection'
    WORKFLOW_4_STEP_2b         = 'dat_website_helpdesk.step_wf4_receiving'
    WORKFLOW_4_STEP_3          = 'dat_website_helpdesk.step_wf4_plan_deployment'
    WORKFLOW_4_STEP_4          = 'dat_website_helpdesk.step_wf4_receive_equipment_docs'
    WORKFLOW_4_STEP_5          = 'dat_website_helpdesk.step_wf4_dat_deploy_tech_solution_and_handle_errors'
    WORKFLOW_4_STEP_6          = 'dat_website_helpdesk.step_wf4_handover_solution'
    WORKFLOW_4_STEP_7          = 'dat_website_helpdesk.step_wf4_acceptance_completion'
    WORKFLOW_4_STEP_FOLLOW_UP  = 'dat_website_helpdesk.step_wf4_follow_up'


    name = fields.Char('Ticket ID', compute='_compute_name', store=True)
    user_has_group_helpdesk_admin = fields.Boolean(
        compute='_compute_user_has_group_helpdesk_admin',
        string='User has group helpdesk admin')
    create_source = fields.Selection([
        ('dat', 'DAT'),
        ('mobile', 'Mobile'),
        ('web_management', 'Web Management'),
        ('portal', 'Portal')
    ],
        default='web_management',
        required=True)
    name_sequence = fields.Char('Ticket ID sequence')
    # Requester Info Group
    customer_id = fields.Many2one('res.partner', string='Customer Name', required=True, tracking=True)
    customer_code = fields.Char('Customer Code', related='customer_id.card_code', tracking=True)
    customer_contact_name = fields.Char(string='Contact Name', tracking=True)
    customer_company_name = fields.Char(string='Company Name', tracking=True)
    customer_phone = fields.Char('Customer Phone', required=True, tracking=True)
    customer_email = fields.Char('Customer Email', tracking=True)
    customer_address = fields.Char('Customer Address', tracking=True)
    customer_has_stock_lot = fields.Boolean(string='Customer Has Stock Lot', compute='_compute_customer_has_stock_lot')
    # Onwer Info Group
    owner_id = fields.Many2one('res.partner', string='Owner Name', related='stock_lot_id.owner_id', readonly=False,
                               tracking=True)
    owner_phone = fields.Char('Owner Phone', related='owner_id.phone', readonly=False, tracking=True)
    owner_email = fields.Char('Owner Email', related='owner_id.email', readonly=False, tracking=True)
    owner_address = fields.Char('Owner Address', tracking=True)

    subject = fields.Text('Subject', required=True)
    description = fields.Text('Description')
    stock_lot_id = fields.Many2one('stock.lot', string='Serial Number', required=False, tracking=True)
    priority_id = fields.Many2one('ticket.priority',
                                  string='Priority', required=True,
                                  default=lambda self: self.env['ticket.priority'].search([('default', '=', True)],
                                                                                          limit=1))
    priority_external_id = fields.Char(string='Priority Name', compute='_compute_priority_external_id')
    step_id = fields.Many2one('ticket.step', string='Step',
                              tracking=True,
                              group_expand='_read_group_step_ids')
    user_id = fields.Many2one('res.users',
                              default=lambda self: self.env.user,
                              check_company=True,
                              index=True, tracking=True, string='User')
    start_date = fields.Datetime('Start Date')
    end_date = fields.Datetime('End Date')
    color = fields.Integer(string="Color")
    replied_date = fields.Datetime('Replied date')
    ticket_type_id = fields.Many2one('helpdesk.type',
                                     string='Ticket Type')
    ticket_type_id_domain = fields.Binary(string="Ticket Type Domain", compute="_compute_ticket_type_id_domain")
    ticket_step_assignee_ids = fields.One2many('ticket.step.assignee', 'ticket_id',
                                               compute='_compute_ticket_step_assignee_ids', store=True)
    assigned_user_id = fields.Many2one(
        'res.users',
        string='Assigned User',
        domain=lambda self: [('groups_id', 'in', self.env.ref(
            'dat_website_helpdesk.helpdesk_user').id)],
        tracking=True)
    assigned_follower_ids = fields.Many2many(
        'res.users',
        string='Followers',
        domain=lambda self: [('groups_id', 'in', self.env.ref(
            'dat_website_helpdesk.helpdesk_user').id)],
        tracking=True)
    service_action = fields.Selection([
        ('warranty_at_dat', 'Warranty At DAT'),
        ('repair_at_dat', 'Repair At DAT (Paid)'),
        ('warranty_onsite', 'Warranty Onsite'),
        ('repair_onsite', 'Repair Onsite (Paid)'),
        ('warranty_at_dat_paid', 'Warranty At DAT (Paid)'),
        ('warranty_onsite_paid', 'Warranty Onsite (Paid)'),
        ('online_technical_support', 'Online Technical Support'),
        ('new_installation_onsite', 'New installation Onsite'),
        ('product_return', 'Product Return'),
        ('request_return', 'Request Return'),
        ('onsite_technical_support', 'Onsite Technical Support')], string='Solution', compute='_compute_service_action',
        store=True)
    service_action_invisible = fields.Boolean(string='Service Action Invisible', default=False)
    request_return_reason = fields.Text(string='Request Return Reason')
    state_id = fields.Many2one("res.country.state", string='State', ondelete='restrict',
                               domain=lambda self: [('country_id', '=',
                                                     self.env.ref('base.vn').id)])
    branch = fields.Many2one('res.company', string='Branch', compute_sudo=True,
                             domain=lambda self: [('id', 'in', self.sudo().env.ref('base.main_company').child_ids.ids)])
    department_id = fields.Many2one(
        HR_DEPARTMENT_MODEL,
        string='Department',
        domain="[('company_id', '=', branch)]",
    )
    team_id = fields.Many2one(
        HR_DEPARTMENT_MODEL,
        string='Team',
        related='department_id',
        store=True,
        readonly=False,
        help="Compatibility field for legacy ticket rules that still reference team_id.",
    )
    department_name = fields.Char(string='Department Name', related='department_id.name')
    attachment_ids = fields.One2many('ir.attachment', 'res_id', string='Attachments', tracking=True)
    active = fields.Boolean(default=True, string='Active')
    ticket_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_ticket_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Ticket Attachment",
        tracking=True
    )
    ticket_note = fields.Text(string='Note')

    customer_rating = fields.Selection(RATING, default='0', readonly=True)
    review = fields.Char('Review', readonly=True)
    status = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
        ('on_hold', 'On Hold')], default='new', compute='_compute_status', store=True, readonly=False)
    ticket_source = fields.Selection([
        ('internal', 'Internal'),
        ('portal', 'Customer Portal'),
        ('api', 'API'),
    ], string='Ticket Source', default='internal')
    reject_reason = fields.Text(string='Reject Reason')
    on_hold_reason = fields.Text(string='On Hold Reason')
    workflow_id = fields.Many2one('helpdesk.workflow', string='Workflow', readonly=True)
    sale_order_ids = fields.One2many('sale.order', 'ticket_id', string='Sale Order')
    is_need_new_so = fields.Boolean(string='Need new SO', default=False)
    step_external_id = fields.Char(compute='_compute_step_external_id')
    wf_external_id = fields.Char(string='Workflow External ID', compute='_compute_workflow_external_id', store=True)
    ticket_type_external_id = fields.Char(compute='_compute_ticket_type_external_id')
    sale_order_feedback = fields.Selection([('agree', 'Agree'), ('refuse', 'Refuse')], string='Sale Order Feedback',
                                           default=False)
    sale_order_feedback_comment = fields.Text(string='Sale Order Feedback Comment')
    sap_dxvt_order_number = fields.Text(string='SAP ĐXVT Number', tracking=True)
    sap_sale_order_number = fields.Text(string='SAP SO Number', tracking=True)
    sap_voucher_type = fields.Selection(
        selection=[
            ("1350", "BH-03E Dispatch For Repair"),
            ("1360", "BH-03F Dispatch For Warranty"),
        ],
        string="SAP Voucher Type",
        default="1350",
        tracking=True,
    )
    sap_reason_id = fields.Many2one(
        "sap.voucher.reason",
        string="Lý do chứng từ",
        domain="[('voucher_type', '=', sap_voucher_type), ('active', '=', True), ('code', 'not in', ['04-994', '04-995'])]",
        tracking=True,
    )
    replace_serial_number = fields.Char(string='Replace Serial Number', tracking=True)
    delivery_address = fields.Char(string='Delivery Address', tracking=True)
    require_materials = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Require Materials', tracking=True)
    require_on_site_installation = fields.Selection([('yes', 'Yes'), ('no', 'No')],
                                                    string='Require On-Site Installation', tracking=True)

    # Kept for compatibility with database views until this module is upgraded.
    salesperson_allowed_company_ids = fields.Many2many(
        'res.company',
        compute='_compute_salesperson_allowed_company_ids',
        string='Salesperson Allowed Companies',
    )
    salesperson_sales_department_ids = fields.Many2many(
        HR_DEPARTMENT_MODEL,
        compute='_compute_salesperson_sales_department_ids',
        string='Salesperson Sales Departments',
    )
    saleperson_id = fields.Many2one('hr.employee', string='Salesperson', tracking=True)
    saleperson_display_name = fields.Char(
        compute='_compute_saleperson_display_name',
        compute_sudo=True,
        string='Salesperson',
    )
    saleperson_deparment_id = fields.Many2one(HR_DEPARTMENT_MODEL, related='saleperson_id.department_id',
                                              string='Salesperson Department')
    saleperson_branch = fields.Many2one('res.company', related='saleperson_id.company_id', string='Salesperson Branch')
    saleperson_sap_slp_code = fields.Integer(
        compute='_compute_saleperson_sap_metadata',
        string='Salesperson SAP Slp Code',
        readonly=True,
    )
    saleperson_sap_business_area = fields.Char(
        compute='_compute_saleperson_sap_metadata',
        string='Salesperson SAP Business Area',
        readonly=True,
    )

    @api.depends_context('uid')
    def _compute_salesperson_allowed_company_ids(self):
        allowed_companies = self.env.user.company_ids
        for ticket in self:
            ticket.salesperson_allowed_company_ids = allowed_companies

    @api.depends_context('uid')
    def _compute_salesperson_sales_department_ids(self):
        sales_departments = self.env[HR_DEPARTMENT_MODEL].browse([
            self.env.ref('dat_website_helpdesk.dep_sale_mb').id,
            self.env.ref('dat_website_helpdesk.dep_sale_mt').id,
            self.env.ref('dat_website_helpdesk.dep_sale_mn').id,
        ])
        for ticket in self:
            ticket.salesperson_sales_department_ids = sales_departments

    @api.depends('saleperson_id')
    def _compute_saleperson_display_name(self):
        for ticket in self:
            ticket.saleperson_display_name = ticket.saleperson_id.display_name or False

    @api.depends('saleperson_id')
    def _compute_saleperson_sap_metadata(self):
        for ticket in self:
            salesperson = ticket.sudo().saleperson_id
            ticket.saleperson_sap_slp_code = getattr(salesperson, 'sap_slp_code', 0) or 0
            ticket.saleperson_sap_business_area = getattr(salesperson, 'sap_business_area', False) or ''

    warranty = fields.Boolean(string='Warranty', default=False)
    warranty_start_date = fields.Datetime(string='Warranty Date', readonly=True)
    warranty_end_date = fields.Datetime(string='Warranty End Date', readonly=True)
    warranty_service_type = fields.Selection([
        ('repair', 'Repair'),
        ('replace', 'Replace'),
        ('replace_with_new_board', 'Replace with new board'),
        ('replace_with_old_board', 'Replace with old board'),
        ('clean_and_load_test', 'Clean & load test'),
    ], string='Warranty Service Type')
    status_after_repair = fields.Char(string='Status After Repair')
    status_before_repair = fields.Char(string='Status Before Repair')
    ir_attachment_warranty_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_ir_attachment_warranty_rel',
        'ticket_id', 'attachment_id',
        string="Upload File", tracking=True,
    )

    reassembly = fields.Boolean(string='Reassembly to Original State')
    reassembly_to_original_description = fields.Text(string='Description')
    reassembly_to_original_image = fields.Binary(string='Image')
    reassembly_to_original_note = fields.Text(string='Note')

    appointment = fields.Boolean(string='Appointment')
    expect_appointment_date = fields.Datetime(string='Expected Appointment Date', tracking=True)
    appointment_note = fields.Text(string='Appointment Note')
    stock_name = fields.Char(related='stock_lot_id.name', string='Stock Name', store=True)
    product_id = fields.Many2one(related='stock_lot_id.product_id', string='Product', store=True)
    product_error_description = fields.Char(string='Product Error Description')
    need_board_serial = fields.Boolean(string='Cần nhập số seri bo')
    board_serial_line_ids = fields.One2many(
        'ticket.board.serial.line',
        'ticket_id',
        string='Số seri bo',
    )
    board_serial_search = fields.Char(
        string='Số seri bo',
        compute='_compute_board_serial_search',
        search='_search_board_serial_search',
    )
    ticket_product_image_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_product_image_rel',
        'ticket_id', 'attachment_id',
        string="Product Error Images",
        tracking=True
    )
    product_error_note = fields.Text(string='Product Error Note')
    product_warranty_status = fields.Selection([('warranty', 'Warranty'), ('out_of_warranty', 'Out of Warranty'),
                                                ('not_eligible_for_warranty', 'Not eligible for warranty')],
                                               string='Product Warranty Status',
                                               compute='_compute_product_warranty_status', store=True)
    product_warranty_reject_reason = fields.Text(string='Product Warranty Reject Reason')
    product_warranty_start_date = fields.Datetime(related='stock_lot_id.warranty_start_date',
                                                  string='Product Warranty Start Date')
    product_warranty_end_date = fields.Datetime(related='stock_lot_id.warranty_end_date',
                                                string='Product Warranty End Date')
    request_type = fields.Selection([('warranty', 'Warranty'), ('repair', 'Repair')], string='Request Type',
                                    compute='_compute_request_type', store=True)

    quotation_expected_date = fields.Date(string='Quotation Expected Date')
    complete_expected_date = fields.Date(string='Completion Expected Date')
    delivery_expected_date = fields.Date(string='Delivery Expected Date')
    installation_expected_date = fields.Date(string='Installation Expected Date')

    next_step_button_invisible = fields.Boolean(string='Next Step Button Invisible',
                                                compute='_compute_next_step_button')
    next_step_button_name = fields.Selection(
        [('next_step', 'Next Step'), ('go_to_location', 'Go to location'), ('start_work', 'Start work'),
         ('done', 'Done'), ('return', 'Return')]
        , string='Next Step Button Name', compute='_compute_next_step_button')
    create_quotation_button_name = fields.Selection(
        [('create_quotation', 'Create Quotation'),
         ('create_material_dispatch', 'Create Material Dispatch')],
        default='create_quotation',
        string='Create Quotation Button Name', compute='_compute_create_quotation_button_name')
    parent_id = fields.Many2one('ticket.helpdesk', string='Parent Ticket')
    child_ids = fields.One2many('ticket.helpdesk', 'parent_id', string='Child Tickets')

    # Workflow 2 field
    lat_move_start = CustomFloat(string='Latitude Move Start')
    lng_move_start = CustomFloat(string='Longitude Move Start')
    addr_move_start = fields.Text(string='Address Move Start')
    lat_move_end = CustomFloat(string='Latitude End')
    lng_move_end = CustomFloat(string='Longitude End')
    addr_move_end = fields.Text(string='Address Move End')
    wf2_status_before_flag = fields.Boolean(string='Status Before Flag', default=False)
    product_status_before = fields.Text(string='Product Status Before')
    note_before = fields.Text(string='Note')
    product_status_image_before_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_product_status_image_before_rel',
        'ticket_id', 'attachment_id',
        string="Product Error Images Before"
    )
    wf2_status_after_flag = fields.Boolean(string='Status After Flag', default=False)
    product_status_after = fields.Text(string='Product Status After')
    note_after = fields.Text(string='Note')
    product_status_image_after_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_product_status_image_after_rel',
        'ticket_id', 'attachment_id',
        string="Product Error Images After"
    )

    origin_sale_order = fields.Char(string='Origin Sale Order')
    install_address = fields.Char(string='Install Address')
    install_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_install_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Install Attachment",
        tracking=True
    )
    install_note = fields.Text(string='Note')

    approved_by = fields.Many2one('res.users', string='Approved By')
    approved_date = fields.Datetime(string='Approved Date')
    # Workflow 3 field
    next_step_assigned_user_id = fields.Many2one('res.users', string='Next Step Assigned User', tracking=True)
    completed_task_description = fields.Text(string='Completed Task Description', tracking=True)
    survey_type = fields.Selection([('online', 'Online'), ('offline', 'Offline')], string='Survey Type', tracking=True)
    expected_survey_date = fields.Datetime(string='Expected Survey Date', tracking=True)
    next_expected_survey_date = fields.Datetime(string='Next Expected Survey Date', tracking=True)
    address_onsite_survey = fields.Char('Address Onsite Survey', tracking=True)
    survey_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_survey_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Survey Attachment",
        tracking=True
    )
    survey_note = fields.Text(string='Note')

    reception_note = fields.Text(string='Note')
    reception_project_code = fields.Text(string='Project Code', tracking=True)
    reception_project_link = fields.Char(string='Project Link', tracking=True)

    survey_result_description = fields.Text(string='Survey Result Description', tracking=True)
    survey_result_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_survey_result_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Survey Result Attachment",
        tracking=True
    )
    survey_result_link = fields.Char(string='Survey Result Link', tracking=True)
    survey_result_note = fields.Text(string='Note', tracking=True)
    bnk_warehouse_side = fields.Selection(
        [('main', 'BH'), ('lt', 'BH (LT)')],
        string='BnK Warehouse Side',
        copy=False,
        readonly=True,
        tracking=True,
    )
    bnk_last_api = fields.Char(string='BnK Last API', copy=False, readonly=True)
    bnk_last_success_at = fields.Datetime(string='BnK Last Success', copy=False, readonly=True)
    survey_branch = fields.Char(string='Survey Branch', tracking=True)
    survey_branch_note = fields.Text(string='Survey Branch Note', tracking=True)
    consultation_approval_note = fields.Text(string='Consultation Approval Note', tracking=True)
    require_technical_solution_design = fields.Selection([('yes', 'Yes'), ('no', 'No')],
                                                         string='Require Technical Solution Design', tracking=True)
    check_is_approved_survey = fields.Selection([('yes', 'Approved Survey'), ('no', 'Rejected Survey')],
                                                string='Check Is Approved Survey', default='yes')
    task_type = fields.Selection([
        ('consulting', 'Tư vấn'),
        ('survey', 'Khảo sát'),
        ('technical_support', 'Hỗ trợ kỹ thuật'),
        ('troubleshooting', 'Xử lý lỗi'),
    ], string='Task Type')
    product_brand = fields.Selection([
        ('invt', 'INVT'),
        ('siemens', 'Siemens'),
        ('sungrow', 'Sungrow'),
        ('goodwe', 'Goodwe'),
        ('pylontech', 'Pylontech'),
        ('lithium_valley', 'Lithium Valley'),
        ('sokoyo', 'Sokoyo'),
        ('solax', 'Solax'),
        ('other', 'Khác'),
    ], string='Product Brand')
    product_line = fields.Selection([
        ('on_grid', 'On-Grid'),
        ('hybrid', 'Hybrid'),
        ('solar_light', 'Solar light'),
        ('ups', 'UPS'),
        ('battery', 'Battery'),
        ('ess', 'ESS'),
        ('bess', 'BESS'),
        ('solar_pump', 'Solar pump'),
    ], string='Product Line')

    # Workflow 4 field
    technical_solution_result = fields.Text(string='Technical Solution Result', tracking=True)
    technical_solution_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_technical_solution_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Technical Solution Attachment",
        tracking=True
    )
    technical_solution_note = fields.Text(string='Note', tracking=True)
    technical_solution_link = fields.Char(string='Technical Solution Link', tracking=True)
    materials_supplier = fields.Selection([('dat', 'DAT Internal'), ('customer', 'Customer')],
                                          string='Material Supplier', tracking=True)
    implementer = fields.Selection([('dat', 'DAT'), ('customer', 'Customer'), ('no_implement', 'No Implement')],
                                   string='Implementer', tracking=True)
    implementation_address_reality = fields.Char(string='Implementation Address Reality', tracking=True)
    delivery_solution_address = fields.Char(string='Delivery Solution Address', tracking=True)
    need_approval = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Need Approval')

    io_number = CustomFloat(string='I/O Number', digits=(16, 2), tracking=True)
    io_range_id = fields.Many2one(
        comodel_name='ticket.helpdesk.io.range',
        string='IO Category',
        readonly=True,
        copy=False,
        help='Automatically set based on IO Quantity and the current ranges'
    )
    inverter_point = CustomFloat(string='Inverter Point', digits=(16, 2), tracking=True)
    servo_point = CustomFloat(string='Servo Point', digits=(16, 2), tracking=True)
    plc_point = CustomFloat(string='PLC Point', digits=(16, 2), tracking=True)
    cabinet_enclosure_point = CustomFloat(string='Cabinet Enclosure Point', digits=(16, 2), tracking=True)
    hmi_point = CustomFloat(string='HMI Point', digits=(16, 2), tracking=True)
    solution_total_point = fields.Float(string='Solution Total Point', compute='_compute_solution_total_point',
                                        store=True)

    project_complexity = fields.Selection([('1', '1'), ('1.25', '1.25'), ('1.5', '1.5'), ('1.75', '1.75'), ('2', '2')],
                                          string='Project Complexity', tracking=True)

    installation_capacity = CustomFloat(string='Installed Capacity', digits=(16, 2), default=None, tracking=True)
    solution_total_point_with_complexity = fields.Float(string='Solution Total Point With Complexity',
                                                        compute='_compute_solution_total_point_with_complexity',
                                                        store=True)
    evaluate_domain = fields.Boolean(string="Evaluate Domain", compute='_compute_evaluate_domain', store=True)

    technical_solution_approval_multiplier = fields.Selection([('1', '1'), ('1.5', '1.5'), ('2', '2')],
                                                              string='Technical Solution Approval Multiplier',
                                                              tracking=True)
    technical_solution_approval_multipliers = fields.Float(string='Technical Solution Approval Multiplier',
                                                              tracking=True)
    
    technical_solution_approval_note = fields.Text(string='Technical Solution Approval Note', tracking=True)
    check_is_approved_techical_solution = fields.Selection(
        [('yes', 'Approved Technical Solution'), ('no', 'Rejected Technical Solution')],
        string='Check Is Approved Technical Solution', default='yes')

    quotation_task_result = fields.Text(string='Quotation Task Result', tracking=True)
    quotation_task_note = fields.Text(string='Note', tracking=True)
    quotation_task_link = fields.Char(string='Quotation Task Link', tracking=True)
    quotation_approval_result = fields.Selection([('successful', 'Successful'), ('resurvey', 'Request re-survey'),
                                                  ('change_technical_solution', 'Request to change Technical Solution'),
                                                  ('rejected', 'Rejected')], string='Quotation Approval Result',
                                                 tracking=True)

    quotation_reject_reason = fields.Selection(
        [('high_price', 'High price'), ('not_appropriate', 'The technical solution is not appropriate/optimal'),
         ('reference', 'For reference only'), ('other', 'Other')], string='Quotation Task Reject Reason', tracking=True)
    quotation_reject_reason_other = fields.Char(string='Quotation Task Reject Reason (Other)', tracking=True)
    quotation_reject_note = fields.Text(string='Quotation Task Reject Note', tracking=True)

    expected_implementation_date = fields.Datetime(string='Expected Implementation Date', tracking=True)
    confirm_expected_implementation_date = fields.Boolean(string='Confirm Expected Implementation Date', default=False)
    expected_implementation_address = fields.Char(string='Expected Implementation Address', tracking=True)
    implementation_note = fields.Text(string='Implementation Note')
    equipment_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_equipment_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Equipment Attachment",
        tracking=True
    )
    technical_solution_design_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_technical_solution_design_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Technical Solution Design Attachment",
        tracking=True
    )
    materials_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_materials_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Materials Attachment",
        tracking=True
    )
    implementation_result = fields.Selection([('error', 'Error'), ('no_error', 'No Error')],
                                             string='Implementation Result', tracking=True)
    implementation_work_ids = fields.One2many('implementation.work', 'ticket_id', string='Checklist Work')
    implementation_work_note = fields.Text(string='Implementation Note', tracking=True)
    implementation_error_ids = fields.One2many(
        comodel_name='ticket.helpdesk.error',
        inverse_name='ticket_id',
        string='Errors',
    )
    total_error_days = fields.Integer(
        string='Total Error Days',
        compute='_compute_total_error_days',
        store=True,
    )
    total_error_days_after_acceptance = fields.Integer(
        string='Total Error Days After Acceptance',
        compute='_compute_total_error_days_after_acceptance',
        store=True,
    )
    implementation_error_description = fields.Text(string='Implementation Error Description')
    implementation_error_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_implementation_error_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Implementation Error Attachment",
        tracking=True
    )

    handover_result = fields.Text(string='Handover Result', tracking=True)
    handover_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_handover_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Handover Attachments",
        tracking=True
    )
    handover_note = fields.Text(string='Handover Note', tracking=True)

    acceptance_result = fields.Text(string='Acceptance Result', tracking=True)
    is_project_file_completed = fields.Boolean(
        string='Is Project File Completed',
        tracking=True,
    )
    acceptance_hsda_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_acceptance_hsda_attachment_rel',
        'ticket_id', 'attachment_id',
        string="HSDA Attachment",
        tracking=True
    )
    acceptance_note = fields.Text(string='Acceptance Note', tracking=True)
    acceptance_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_acceptance_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Acceptance Attachment",
        tracking=True
    )
    acceptance_design_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_acceptance_design_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Acceptance Design Attachment",
        tracking=True
    )
    acceptance_report_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_acceptance_report_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Acceptance Report Attachment",
        tracking=True
    )
    acceptance_project_revenue = CustomFloat(
        string='Project Revenue',
        digits=(16, 2),
        tracking=True)
    acceptance_dvkt_revenue = CustomFloat(
        string='Technical Service Revenue',
        digits=(16, 2),
        tracking=True)
    acceptance_quotation_attachment_ids = fields.Many2many(
        'ir.attachment',
        'ticket_helpdesk_acceptance_quotation_attachment_rel',
        'ticket_id', 'attachment_id',
        string="Acceptance Quotation Attachment",
        tracking=True
    )

    check_reception = fields.Boolean(string='Check Reception', default=False)
    check_action_assign = fields.Boolean(string='Check Action Assign', default=False)
    need_button_approve = fields.Boolean(string='Need to click button approve', default=False)
    sap_so_status = fields.Char(
        string='SAP SO Status',
        compute="_compute_sap_so_status",
        store=True,
        help="Status of the Sale Order in SAP")
    note_SO = fields.Char(string='Note SO', tracking=True)

    ticket_rating = fields.Many2one(
        'ticket.rating',
        string='Customer Rating')
    ticket_rating_rate = fields.Integer(related='ticket_rating.rate', store=True)
    ticket_rating_note = fields.Text(related='ticket_rating.note', store=True)
    popup_notification = fields.Char(
        string='Popup Notification',
        help='Temporary field to store popup notification message',
        readonly=True,
        store=False
    )

    number_of_sale_cabinets = fields.Integer(string='Number of Sale Cabinets', default=1, tracking=True)
    is_derpartment_auto = fields.Boolean(
        string='Is Derpartment Auto',
        default=False,
        compute="_compute_is_derpartment_auto")
    
    is_derpartment_energy = fields.Boolean(
        string='Is Derpartment Energy',
        default=False,
        compute="_compute_is_derpartment_energy")

    is_exchange_1_1 = fields.Boolean(string="Đổi 1-1")
    is_return_defective = fields.Boolean(string="Trả hàng lỗi")

    @api.constrains("is_exchange_1_1", "is_return_defective")
    def _check_replace_return_flags(self):
        for r in self:
            if r.is_exchange_1_1 and r.is_return_defective:
                raise ValidationError(_("Chỉ được chọn 1 trong 2: Đổi 1-1 hoặc Trả hàng lỗi."))

        # ===== ĐỔI 1-1: bắt buộc xác nhận nhận SP lỗi + chọn serial mới =====
    is_received_defective = fields.Boolean(string="Đã nhận sản phẩm lỗi", tracking=True)
    received_defective_date = fields.Datetime(string="Ngày nhận SP lỗi", tracking=True)

    new_stock_lot_id = fields.Many2one(
        "stock.lot",
        string="Serial mới (đổi 1-1)",
        tracking=True,
        domain="[('product_id', '=', product_id)]",
        help="Chọn serial mới trong kho để giao đổi 1-1."
    )
    new_serial_number = fields.Char(
        string="Serial mới",
        related="new_stock_lot_id.name",
        store=True,
        readonly=True
    )

    @api.onchange("new_stock_lot_id")
    def _onchange_new_stock_lot_id(self):
        for r in self:
            # giữ tương thích với field cũ replace_serial_number (Char) đang dùng nhiều chỗ
            r.replace_serial_number = r.new_stock_lot_id.name if r.new_stock_lot_id else False

    @api.depends('board_serial_line_ids.old_board_serial', 'board_serial_line_ids.new_board_serial')
    def _compute_board_serial_search(self):
        for ticket in self:
            serials = []
            for line in ticket.board_serial_line_ids:
                serials.extend(filter(None, [line.old_board_serial, line.new_board_serial]))
            ticket.board_serial_search = ' '.join(dict.fromkeys(serials))

    def _search_board_serial_search(self, operator, value):
        return [
            '|',
            ('board_serial_line_ids.old_board_serial', operator, value),
            ('board_serial_line_ids.new_board_serial', operator, value),
        ]


    _sql_constraints = [
        ('check_positive_inverter_point', 'CHECK(inverter_point >= 0)',
         'Inverter point must be greater than or equal 0.'),
        ('check_positive_servo_point', 'CHECK(servo_point >= 0)', 'Servo point must be greater than or equal 0.'),
        ('check_plc_point', 'CHECK(plc_point >= 0)', 'PLC point must be greater than or equal 0.'),
        ('check_cabinet_enclosure_point', 'CHECK(cabinet_enclosure_point >= 0)',
         'Cabinet Enclosure point must be greater than or equal 0.'),
        ('check_hmi_point', 'CHECK(hmi_point >= 0)', 'HMI point must be greater than or equal 0.'),
        ('check_installation_capacity', 'CHECK(installation_capacity >= 0)',
         'Installation Capacity must be greater than or equal 0.')
    ]

    @api.constrains('product_warranty_status', 'stock_lot_id')
    def _check_product_warranty_status(self):
        for rec in self:
            if not rec.product_warranty_status:
                continue
            
            # Ngày hết hạn bảo hành:
            # - Nếu có trên lô thì dùng
            # - Nếu không có thì mặc định 01/01/2000
            warranty_end_date = rec._get_product_warranty_end_date()
            if not warranty_end_date:
                continue
            end_dt = fields.Datetime.to_datetime(warranty_end_date)
    
            # Ngày tạo phiếu (đã là datetime)
            create_dt = fields.Datetime.to_datetime(rec.create_date)
    
            # Nếu đang chọn "còn bảo hành" / "không đủ điều kiện bảo hành"
            # mà ngày tạo > ngày hết hạn -> sai
            if rec.product_warranty_status in ['warranty', 'not_eligible_for_warranty'] and create_dt > end_dt:
                raise ValidationError(
                    _("The product warranty status of ticket %s is not valid. "
                      "The warranty period has expired.") % rec.name
                )
    
            # Nếu đang chọn "hết bảo hành" mà ngày tạo <= ngày hết hạn -> sai
            if rec.product_warranty_status == 'out_of_warranty' and create_dt <= end_dt:
                raise ValidationError(
                    _("The product warranty status of ticket %s is not valid. "
                      "The product is still under warranty.") % rec.name
                )

    def _get_product_warranty_end_date(self):
        self.ensure_one()
        lot = self.stock_lot_id
        if not lot:
            return False
        return lot.warranty_end_date or getattr(lot, 'manufacturer_warranty_end_date', False)


    @api.constrains('quotation_expected_date', 'complete_expected_date', 'delivery_expected_date',
                    'installation_expected_date')
    def _check_dates(self):
        today = date.today()
        for record in self:
            if record.quotation_expected_date and record.quotation_expected_date < today:
                raise ValidationError(_('Quotation Expected Date must be greater than or equal to today.'))
            if record.complete_expected_date and record.complete_expected_date < today:
                raise ValidationError(_('Completion Expected Date must be greater than or equal to today.'))
            if record.delivery_expected_date and record.delivery_expected_date < today:
                raise ValidationError(_('Delivery Expected Date must be greater than or equal to today.'))
            if record.installation_expected_date and record.installation_expected_date < today:
                raise ValidationError(_('Installation Expected Date must be greater than or equal to today.'))

    @api.constrains('customer_phone')
    def _check_customer_phone(self):
        if self.env.context.get('skip_phone_validation_from_create_ticket_wizard'):
            return
        for rec in self:
            if rec.customer_phone and not is_valid_phone_number(rec.customer_phone):
                raise ValidationError(
                    _("The customer phone number of ticket %s is not valid. Please check again.") % rec.name)

    @api.constrains('owner_phone')
    def _check_owner_phone(self):
        if self.env.context.get('skip_phone_validation_from_create_ticket_wizard'):
            return
        for rec in self:
            if rec.owner_phone and not is_valid_phone_number(rec.owner_phone):
                raise ValidationError(
                    _("The owner phone number of ticket %s is not valid. Please check again.") % rec.name)

    @api.depends_context('uid')
    def _compute_user_has_group_helpdesk_admin(self):
        user_has_group_helpdesk_admin = self.user_has_groups('dat_website_helpdesk.helpdesk_admin')
        for ticket in self:
            ticket.user_has_group_helpdesk_admin = user_has_group_helpdesk_admin

    @api.depends('inverter_point', 'servo_point', 'plc_point', 'cabinet_enclosure_point', 'hmi_point')
    def _compute_solution_total_point(self):
        for rec in self:
            rec.solution_total_point = (rec.inverter_point or 0) + (rec.servo_point or 0) + (rec.plc_point or 0) + (
                    rec.cabinet_enclosure_point or 0) + (rec.hmi_point or 0)
            
    @api.depends('department_id')
    def _compute_is_derpartment_auto(self):
        for rec in self:
                auto_department = [
                    self.env.ref('dat_website_helpdesk.dep_automation_mb').id,
                    self.env.ref('dat_website_helpdesk.dep_automation_mt').id,
                    self.env.ref('dat_website_helpdesk.dep_automation_mn').id
                ]
                if rec.department_id.id in auto_department:
                    rec.is_derpartment_auto = True
                else:
                    rec.is_derpartment_auto = False

    @api.depends('department_id')
    def _compute_is_derpartment_energy(self):
        for rec in self:
            energy_department = [
                self.env.ref('dat_website_helpdesk.dep_energy_mb').id,
                self.env.ref('dat_website_helpdesk.dep_energy_mt').id,
                self.env.ref('dat_website_helpdesk.dep_energy_mn').id
            ]
            if rec.department_id.id in energy_department:
                rec.is_derpartment_energy = True
            else:
                rec.is_derpartment_energy = False

    @api.depends('solution_total_point', 'project_complexity', 'installation_capacity',
                 'technical_solution_approval_multipliers')
    def _compute_solution_total_point_with_complexity(self):
        for rec in self:
            complexity = float(
                rec.technical_solution_approval_multipliers or 1.0) if rec.workflow_id == self.env.ref(
                self.WORKFLOW_3) else float(
                rec.project_complexity or 1.0)
            if rec.evaluate_domain:
                total_point = rec.solution_total_point or 0
            else:
                total_point = rec.installation_capacity or 0
            rec.solution_total_point_with_complexity = total_point * complexity

    @api.depends('department_id')
    def _compute_evaluate_domain(self):
        for rec in self:
            energy_department = [
                self.env.ref('dat_website_helpdesk.dep_energy_mb').id,
                self.env.ref('dat_website_helpdesk.dep_energy_mt').id,
                self.env.ref('dat_website_helpdesk.dep_energy_mn').id
            ]
            if rec.department_id.id in energy_department:
                rec.evaluate_domain = False
            else:
                rec.evaluate_domain = True

    @api.depends('ticket_type_id')
    def _compute_ticket_type_external_id(self):
        for rec in self:
            external_ids = rec.ticket_type_id._get_external_ids()
            external_id = [x.split(".")[1] for x in external_ids.get(rec.ticket_type_id.id, []) if
                           x.split(".")[0] == 'dat_website_helpdesk']
            rec.ticket_type_external_id = external_id[0] if external_id else False

    @api.depends('sale_order_ids')
    def _compute_sap_so_status(self):
        for rec in self:
            sap_so_status = False
            if rec.sale_order_ids:
                sap_so_status = rec.sale_order_ids[-1].sap_status
            rec.sap_so_status = sap_so_status

    @api.depends('implementation_error_ids.date_detected', 'implementation_error_ids.date_resolved')
    def _compute_total_error_days_after_acceptance(self):
        for ticket in self:
            total = 0
            for err in ticket.implementation_error_ids:
                if err.date_detected and err.date_resolved and err.acceptance_status == 'after_acceptance':
                    start_dt = fields.Datetime.from_string(err.date_detected)
                    end_dt = fields.Datetime.from_string(err.date_resolved)
                    delta_days = (end_dt.date() - start_dt.date()).days + 1
                    if delta_days > 0:
                        total += delta_days
            ticket.total_error_days_after_acceptance = total
    
    @api.depends('implementation_error_ids.date_detected', 'implementation_error_ids.date_resolved')
    def _compute_total_error_days(self):
        for ticket in self:
            total = 0
            for err in ticket.implementation_error_ids:
                if err.date_detected and err.date_resolved:
                    start_dt = fields.Datetime.from_string(err.date_detected)
                    end_dt = fields.Datetime.from_string(err.date_resolved)
                    delta_days = (end_dt.date() - start_dt.date()).days + 1
                    if delta_days > 0:
                        total += delta_days
            ticket.total_error_days = total

    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        if self.customer_id:
            self.customer_contact_name = self.customer_id.name
            self.customer_company_name = self.customer_id.company_name
            self.customer_phone = self.customer_id.phone or self.customer_id.mobile
            self.customer_email = self.customer_id.email
            self.customer_address = self.customer_id.contact_address
            if self.stock_lot_id.owner_id != self.customer_id and self.stock_lot_id.buyer_id != self.customer_id:
                self.stock_lot_id = False

    @api.onchange('owner_id')
    def _onchange_owner_id(self):
        if self.owner_id:
            # Unable to write back contact_address into res.partner
            self.owner_address = self.owner_id.owner_address

    @api.onchange('stock_lot_id')
    def _onchange_stock_lot_id_contacts(self):
        if not self.stock_lot_id:
            return
        lot = self.stock_lot_id
        buyer = lot.buyer_id
        owner = lot.owner_id
        if buyer:
            self.customer_id = buyer
        if owner:
            self.owner_id = owner
            self.owner_phone = lot.owner_phone or owner.mobile
            self.owner_email = owner.email
            self.owner_address = owner.contact_address
            self.customer_contact_name = owner.name
            self.customer_company_name = owner.company_name
            self.customer_phone = (
                lot.owner_phone
                or owner.mobile
                or (lot.buyer_phone if buyer else False)
                or (buyer.mobile if buyer else False)
            )
            self.customer_email = owner.email
            self.customer_address = owner.contact_address
        elif buyer:
            self.customer_contact_name = buyer.name
            self.customer_company_name = buyer.company_name
            self.customer_phone = lot.buyer_phone or buyer.mobile
            self.customer_email = buyer.email
            self.customer_address = buyer.contact_address

    @api.depends('product_warranty_status')
    def _compute_request_type(self):
        for rec in self:
            if rec.product_warranty_status == 'warranty':
                rec.request_type = 'warranty'
            elif rec.product_warranty_status == 'out_of_warranty':
                rec.request_type = 'repair'
            else:
                rec.request_type = False

    @api.depends('product_warranty_status', 'ticket_type_id')
    def _compute_service_action(self):
        for rec in self:
            if rec.parent_id:
                continue

            # Define mapping of ticket types and warranty status to service actions
            ticket_mapping = {
                self.env.ref(self.TICKET_TYPE_1).id: {
                    'warranty': 'warranty_at_dat',
                    'out_of_warranty': 'repair_at_dat',
                    'not_eligible_for_warranty': 'warranty_at_dat_paid',
                },
                self.env.ref(self.TICKET_TYPE_2).id: {
                    'warranty': 'warranty_onsite',
                    'out_of_warranty': 'repair_onsite',
                    'not_eligible_for_warranty': 'warranty_onsite_paid',
                },
                self.env.ref(self.TICKET_TYPE_3).id: {
                    'any': 'online_technical_support',
                },
                self.env.ref(self.TICKET_TYPE_4).id: {
                    'any': 'new_installation_onsite',
                },
                self.env.ref(self.TICKET_TYPE_RETURN).id: {
                    'any': 'product_return',
                },
            }

            # Get the ticket type id and the warranty status
            ticket_type_id = rec.ticket_type_id.id
            warranty_status = rec.product_warranty_status

            # Set the service action based on the mapping
            if ticket_type_id in ticket_mapping:
                service_action = ticket_mapping[ticket_type_id].get(warranty_status,
                                                                    ticket_mapping[ticket_type_id].get('any'))
                rec.service_action = service_action

    @api.depends('step_id', 'assigned_user_id')
    def _compute_ticket_step_assignee_ids(self):
        for rec in self:
            assigned_user_to_add = set([rec.assigned_user_id.id]) - set(
                rec.ticket_step_assignee_ids.filtered(lambda status: status.step_id.id == rec.step_id.id).user_id.ids)

            assigned_user_to_remove = set(rec.ticket_step_assignee_ids.filtered(
                lambda status: status.step_id.id == rec.step_id.id).user_id.ids) - set([rec.assigned_user_id.id])

            if assigned_user_to_add:
                rec.ticket_step_assignee_ids = [(0, 0, {
                    'user_id': user_id,
                    'step_id': rec.step_id.id,
                }) for user_id in assigned_user_to_add]

            if assigned_user_to_remove:
                rec.ticket_step_assignee_ids = [(2, line.id, 0) for line in rec.ticket_step_assignee_ids if
                                                line.user_id.id in assigned_user_to_remove and line.step_id.id == rec.step_id.id]

    @api.depends('stock_lot_id', 'create_date', 'stock_lot_id.warranty_end_date')
    def _compute_product_warranty_status(self):
        for rec in self:
            rec.product_warranty_status = False
            warranty_end_date = rec._get_product_warranty_end_date()
            if warranty_end_date and rec.create_date:
                if rec.create_date <= warranty_end_date:
                    rec.product_warranty_status = 'warranty'
                else:
                    rec.product_warranty_status = 'out_of_warranty'

    @api.depends('branch.prefix', 'name_sequence')
    def _compute_name(self):
        for rec in self:
            if rec.branch and rec.sudo().branch.prefix and rec.name_sequence:
                rec.name = f"{rec.sudo().branch.prefix}-{rec.name_sequence}"
            else:
                rec.name = rec.name_sequence

    @api.depends('customer_id')
    def _compute_customer_has_stock_lot(self):
        for rec in self:
            rec.customer_has_stock_lot = False
            if rec.customer_id:
                lot_ids = self.env['stock.lot'].search(
                    ['|', ('owner_id', '=', rec.customer_id.id), ('buyer_id', '=', rec.customer_id.id)])
                rec.customer_has_stock_lot = True if lot_ids else False

    @api.depends('step_id', 'status', 'workflow_id')
    def _compute_next_step_button(self):
        for rec in self:
            steps_actions = self._get_steps_actions()
            workflow_id = rec.workflow_id.id
            step_id = rec.step_id.id if rec.step_id else None

            if (not rec.ticket_step_assignee_ids.filtered(
                    lambda line: line.user_id.id == self.env.user.id and line.step_id.id == step_id) \
                or rec.ticket_step_assignee_ids.filtered(
                        lambda line: line.user_id.id == self.env.user.id and line.step_id.id == step_id).done) \
                    and not all(
                rec.ticket_step_assignee_ids.filtered(lambda line: line.step_id.id == step_id).mapped('done')):
                rec.next_step_button_invisible = True
                rec.next_step_button_name = False
            elif (step_id in (self.env.ref(self.WORKFLOW_1_STEP_3).id,
                              self.env.ref(self.WORKFLOW_1_STEP_4).id) and not self.sale_order_ids) or \
                    (step_id == self.env.ref(self.WORKFLOW_1_STEP_4).id
                     and not self.sale_order_ids.filtered(lambda so: so.status == 'confirmed')) or \
                    (step_id == self.env.ref(self.WORKFLOW_3_STEP_8).id and not self.sale_order_ids):
                rec.next_step_button_invisible = True
                rec.next_step_button_name = False
            elif (workflow_id in steps_actions and step_id in steps_actions[
                workflow_id]) and rec.status == 'in_progress' or rec.workflow_id.id in (
                    self.env.ref(self.WORKFLOW_3).id, self.env.ref(self.WORKFLOW_4).id):
                if rec.workflow_id.id == (
                        self.env.ref(self.WORKFLOW_4).id) and rec.check_action_assign and not rec.check_reception:
                    rec.next_step_button_invisible = True
                    rec.next_step_button_name = False
                else:
                    rec.next_step_button_invisible = False
                    if step_id == self.env.ref(self.WORKFLOW_2_STEP_2).id:
                        rec.next_step_button_name = 'go_to_location'
                    elif step_id == self.env.ref(self.WORKFLOW_2_STEP_3).id:
                        rec.next_step_button_name = 'start_work'
                    elif step_id in (self.env.ref(self.WORKFLOW_2_STEP_5).id, self.env.ref(self.WORKFLOW_4_STEP_7).id,
                                     self.env.ref(self.WORKFLOW_4_STEP_FOLLOW_UP).id,
                                     self.env.ref(self.WORKFLOW_RETURN_STEP_COMPLETE).id):
                        rec.next_step_button_name = 'done'
                    else:
                        rec.next_step_button_name = 'next_step'
            else:
                rec.next_step_button_invisible = True
                rec.next_step_button_name = False

    @api.depends('product_warranty_status')
    def _compute_create_quotation_button_name(self):
        for rec in self:
            if rec.workflow_id.id == (
                    self.env.ref(self.WORKFLOW_1).id) and rec.product_warranty_status == 'warranty':
                rec.create_quotation_button_name = 'create_material_dispatch'
            else:
                rec.create_quotation_button_name = 'create_quotation'

    @api.depends('priority_id')
    def _compute_priority_external_id(self):
        for rec in self:
            external_ids = rec.priority_id._get_external_ids()
            external_id = [x.split(".")[1] for x in external_ids.get(rec.priority_id.id, []) if
                           x.split(".")[0] == 'dat_website_helpdesk']
            rec.priority_external_id = external_id[0] if external_id else False

    @api.depends('step_id')
    def _compute_step_external_id(self):
        for rec in self:
            external_ids = rec.step_id._get_external_ids()
            external_id = [x.split(".")[1] for x in external_ids.get(rec.step_id.id, []) if
                           x.split(".")[0] == 'dat_website_helpdesk']
            rec.step_external_id = external_id[0] if external_id else False

    @api.depends('workflow_id')
    def _compute_workflow_external_id(self):
        for rec in self:
            rec.wf_external_id = self.get_wf_external_id(rec.workflow_id)

    def get_wf_external_id(self, workflow_id):
        external_ids = workflow_id._get_external_ids()
        external_id = [x.split(".")[1] for x in external_ids.get(workflow_id.id, []) if
                       x.split(".")[0] == 'dat_website_helpdesk']
        wf_external_id = external_id[0] if external_id else False
        return wf_external_id

    # 1) ONLY Step 9 là bước đóng
    def _get_closed_step(self):
        res = set()
        step_9_id = self._safe_ref_id(getattr(self, "WORKFLOW_1_STEP_9", ""))
        if step_9_id:
            res.add(step_9_id)
        return res
    # 2) Helper: remote = online_technical_support
    def _wf1_is_remote(self):
        self.ensure_one()
        return (self.service_action or "") == "online_technical_support"
    

    @api.depends('step_id')
    def _compute_status(self):
        closed_steps = self._get_closed_step()
        if self.step_id.id in closed_steps:
            self.status = 'closed'
            self.end_date = fields.Datetime.now()

    @api.onchange('service_action', 'product_warranty_status', 'request_type')
    def _onchange_default_sap_voucher_type(self):
        warranty_actions = (
            "warranty_at_dat",
            "warranty_onsite",
            "warranty_at_dat_paid",
            "warranty_onsite_paid",
        )
        for rec in self:
            is_repair = (
                rec.request_type == "repair"
                or rec.product_warranty_status in ("out_of_warranty", "not_eligible_for_warranty")
                or rec.service_action in ("repair_at_dat", "repair_onsite")
            )
            is_warranty = (
                not is_repair
                and rec.product_warranty_status == "warranty"
                and rec.service_action in warranty_actions
            )
            if not rec.sap_voucher_type:
                rec.sap_voucher_type = "1360" if is_warranty else "1350"

    @api.onchange('sap_voucher_type')
    def _onchange_sap_voucher_type_ticket(self):
        for rec in self:
            if rec.sap_reason_id and (
                rec.sap_reason_id.voucher_type != rec.sap_voucher_type
                or rec.sap_reason_id.code in EXCLUDED_SAP_REASON_CODES
                or not rec.sap_reason_id.active
            ):
                rec.sap_reason_id = False

    @api.onchange('branch')
    def _onchange_branch(self):
        if self.branch:
            self.department_id = False

    @api.onchange('department_id')
    def _onchange_department(self):
        for record in self:
            if record.department_id:
                record.assigned_user_id = self.get_assigned_user_id_based_on_department(department=record.department_id,
                                                                                        branch=record.branch,
                                                                                        ticket_type=record.ticket_type_id,
                                                                                        stock_lot=record.stock_lot_id)
                department_ids_to_check = [
                    self.env.ref('dat_website_helpdesk.dep_customer_service_mn').id,
                    self.env.ref('dat_website_helpdesk.dep_customer_service_mb').id,
                    self.env.ref('dat_website_helpdesk.dep_customer_service_mt').id
                ]
                record.service_action_invisible = record.department_id.id not in department_ids_to_check

    def _set_auto_followers_from_mapping(self):
        """Auto-add followers to message_follower_ids based on assignment mapping (branch, department, ticket type)."""
        self.ensure_one()
        if not (self.branch and self.department_id and self.ticket_type_id):
            return

        mapping = self.env['ticket.helpdesk.assignment.follower'].sudo().search([
            ('branch_id', '=', self.branch.id),
            ('department_id', '=', self.department_id.id),
            ('ticket_type_id', '=', self.ticket_type_id.id),
        ], limit=1)

        if not mapping or not mapping.employee_ids:
            return

        helpdesk_users = mapping.employee_ids.sudo().user_id.filtered(
            lambda user: user.groups_id
        )
        if not helpdesk_users:
            return 

        partner_ids = [user.partner_id.id for user in helpdesk_users]
        self.message_subscribe(partner_ids=partner_ids)

    def get_assigned_user_id_based_on_department(self, department=None, branch=None, ticket_type=None, stock_lot=None):
        if not department:
            raise ValidationError(_("Hiện tại chưa có bộ phận phụ trách loại yêu cầu này!"))
        if branch and ticket_type:
            mapping = self.env['ticket.helpdesk.assignment.mapping'].sudo().search([
                ('branch_id', '=', branch.id),
                ('department_id', '=', department.id),
                ('ticket_type_id', '=', ticket_type.id),
            ], limit=1)
            if mapping and mapping.user_id:
                return mapping.user_id

        manager = department.sudo().manager_id
        if manager and manager.user_id:
            return manager.user_id

        return False

    @api.depends('department_id')
    def _compute_ticket_type_id_domain(self):
        for record in self:
            department_ids_to_check = [
                self.env.ref('dat_website_helpdesk.dep_customer_service_mn').id,
                self.env.ref('dat_website_helpdesk.dep_customer_service_mb').id,
                self.env.ref('dat_website_helpdesk.dep_customer_service_mt').id
            ]
            if record.department_id.id in department_ids_to_check:
                valid_type_ids = [self.env.ref(self.TICKET_TYPE_1).id,
                                  self.env.ref(self.TICKET_TYPE_2).id,
                                  self.env.ref(self.TICKET_TYPE_3).id,
                                  self.env.ref(self.TICKET_TYPE_4).id]
                if record.department_id == self.env.ref('dat_website_helpdesk.dep_customer_service_mn'):
                    valid_type_ids.append(self.env.ref(self.TICKET_TYPE_RETURN).id)
                record.ticket_type_id_domain = [('id', 'in', valid_type_ids)]
            else:
                record.ticket_type_id_domain = [('id', 'in', [self.env.ref('dat_website_helpdesk.ticket_type_5').id,
                                                              self.env.ref('dat_website_helpdesk.ticket_type_6').id])]
                
    @api.onchange('owner_id')
    def _onchange_owner_id(self):
        if self.owner_id:
            self.owner_address = self.owner_id.contact_address
            owner_sale_person = self.owner_id.sudo().sale_person
            customer_sale_person = self.customer_id.sudo().sale_person
            if owner_sale_person:
                self.saleperson_id = owner_sale_person
            elif customer_sale_person:
                self.saleperson_id = customer_sale_person
            elif self.branch:
                sale_department_ids = [
                    self.env.ref('dat_website_helpdesk.dep_sale_mb').id,
                    self.env.ref('dat_website_helpdesk.dep_sale_mt').id,
                    self.env.ref('dat_website_helpdesk.dep_sale_mn').id
                ]
                sale_department = self.env[HR_DEPARTMENT_MODEL].search([
                    ('id', 'in', sale_department_ids),
                    ('company_id', '=', self.branch.id)
                ], limit=1)
                if sale_department and sale_department.manager_id:
                    assigned_user = self.get_assigned_user_id_based_on_department(
                        department=sale_department,
                        branch=self.branch,
                        ticket_type=self.ticket_type_id
                    )
                    self.saleperson_id = assigned_user.sudo().employee_id if assigned_user and assigned_user.sudo().employee_id else False
            else:
                self.saleperson_id = False

    @api.onchange('ticket_type_id')
    def _onchange_require_on_site_installation(self):
        for rec in self:
            if rec.step_id in (self.env.ref(self.WORKFLOW_1_STEP_2), self.env.ref(self.WORKFLOW_1_STEP_2b)):
                if rec.ticket_type_id == self.env.ref(self.TICKET_TYPE_2):
                    rec.require_on_site_installation = 'yes'
                else:
                    rec.require_on_site_installation = 'no'

    def auto_close_ticket(self):
        """Automatically closing the ticket"""
        auto_close = self.env['ir.config_parameter'].sudo().get_param(
            'dat_website_helpdesk.auto_close_ticket')
        if auto_close:
            no_of_days = self.env['ir.config_parameter'].sudo().get_param(
                'dat_website_helpdesk.no_of_days')
            records = self.env['ticket.helpdesk'].search([])
            for rec in records:
                days = (fields.Datetime.today() - rec.create_date).days
                if days >= int(no_of_days):
                    close_step_id = self.env['ticket.step'].search(
                        [('closing_step', '=', True)])
                    if close_step_id:
                        rec.step_id = close_step_id

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form':
            related_fields = set(k for k, v in self._fields.items() if v.related and v.readonly)
            for field in arch.xpath("//sheet//field[not(ancestor::field)]"):
                if field.attrib.get('name') in related_fields:
                    readonly_condition = 1
                elif field.attrib.get('name') == 'implementation_error_ids':
                    continue
                else:
                    readonly_condition = field.attrib.get('readonly', "status in ('closed', 'rejected', 'on_hold')")

                field.set('readonly', f"{readonly_condition} or status in ('closed', 'rejected', 'on_hold')")
        return arch, view

    @api.model
    def _read_group_step_ids(self, steps, domain, order):
        """
        return the steps to step_ids
        """
        step_ids = self.env['ticket.step'].search([])
        return step_ids

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = self.clean_vals_list(vals_list)
        for vals in vals_list:
            self._set_name_sequence(vals)
            self._set_name_sequence(vals)
            self._set_assigned_users(vals)
            self._set_wf_external_id(vals)
            self._set_saleperson_id(vals)

        records = super(TicketHelpDesk, self).create(vals_list)

        for rec in records:
            rec.sudo()._onchange_require_on_site_installation()
            rec.sudo()._onchange_department()
            rec.sudo()._compute_service_action()
            rec.sudo()._set_auto_followers_from_mapping()
            rec.sudo()._send_zns_notification(
                'dat_website_helpdesk.zalo_zns_template_noti_customer_when_receive_ticket',
                _('ZNS tiếp nhận phiếu hỗ trợ'),
            )

        return records

    def _apply_io_mapping(self):
        """Helper: find the active range whose bounds include io_number."""
        io_range = self.env['ticket.helpdesk.io.range']
        for ticket in self:
            mapping = io_range.search([
                ('min_qty', '<=', ticket.io_number),
                '|',
                ('max_qty', '=', 0.0),
                ('max_qty', '>=', ticket.io_number),
            ],
                limit=1
            )
            ticket.io_range_id = mapping.id or False

    def _set_name_sequence(self, vals):
        if not vals.get('name_sequence'):
            vals['name_sequence'] = self.env['ir.sequence'].next_by_code('ticket.helpdesk')

    def _set_assigned_users(self, vals):
        department_id = vals.get('department_id')
        branch_id = vals.get('department_id')
        ticket_type_id = vals.get('ticket_type_id')
        stock_lot_id = vals.get('stock_lot_id')
        if department_id:
            department = self.env[HR_DEPARTMENT_MODEL].browse(department_id)
            branch = self.env['res.company'].sudo().browse(branch_id)
            ticket_type = self.env['helpdesk.type'].browse(ticket_type_id)
            stock_lot = self.env['stock.lot'].browse(stock_lot_id) if stock_lot_id else None
            assigned_user_id = self.get_assigned_user_id_based_on_department(department=department, branch=branch,
                                                                             ticket_type=ticket_type,
                                                                             stock_lot=stock_lot)
            if assigned_user_id:
                vals['assigned_user_id'] = assigned_user_id.id

    def _set_wf_external_id(self, vals):
        workflow_id = vals.get('workflow_id')
        if workflow_id:
            workflow = self.env['helpdesk.workflow'].browse(workflow_id)
            vals['wf_external_id'] = self.get_wf_external_id(workflow)

    def _set_saleperson_id(self, vals):
        if not vals.get('saleperson_id') and (vals.get('owner_id') or vals.get('customer_id')) and vals.get('branch'):
            if vals.get('owner_id'):
                owner = self.env['res.partner'].sudo().browse(vals['owner_id'])
                if owner.sale_person:
                    vals['saleperson_id'] = owner.sale_person.id
                    return
            customer = self.env['res.partner'].sudo().browse(vals['customer_id'])
            if customer.sale_person:
                vals['saleperson_id'] = customer.sale_person.id
            else:
                sale_department_ids = [
                    self.env.ref('dat_website_helpdesk.dep_sale_mb').id,
                    self.env.ref('dat_website_helpdesk.dep_sale_mt').id,
                    self.env.ref('dat_website_helpdesk.dep_sale_mn').id
                ]

                sale_department = self.env[HR_DEPARTMENT_MODEL].search([
                    ('id', 'in', sale_department_ids),
                    ('company_id', '=', vals['branch'])
                ], limit=1)

                if sale_department and sale_department.manager_id:
                    vals['saleperson_id'] = self.get_assigned_user_id_based_on_department(department=sale_department,
                                                                                          branch=self.branch,
                                                                                          ticket_type=self.ticket_type_id).id

    def _save_customer_rating(self, rating, note=False):
        self.ensure_one()
        try:
            rating_value = int(rating or 0)
        except (TypeError, ValueError):
            rating_value = 0
        rating_value = max(1, min(rating_value, 5))
        note = note or ''

        vals = {
            'rate': rating_value,
            'note': note,
        }
        if self.ticket_rating:
            self.ticket_rating.sudo().write(vals)
            rating_record = self.ticket_rating
        else:
            rating_record = self.env['ticket.rating'].sudo().create(vals)

        self.with_context(skip_ticket_rating_sync=True).sudo().write({
            'ticket_rating': rating_record.id,
            'customer_rating': str(rating_value),
            'review': note,
        })
        return rating_record

    def pass_changed_fields_to_context(self, vals):
        """
        Collect the changed field labels to use for notification
        and save them to context.
        """
        fields_tracking = {
            'customer_id',
            'customer_phone',
            'subject',
            'stock_lot_id',
            'priority_id',
            'service_action',
            'request_return_reason',
            'branch',
            'description',
            'department_id',
            'ticket_type_id',
            'require_materials',
            'require_on_site_installation',
            'customer_contact_name',
            'owner_id',
            'owner_phone',
            'product_warranty_status',
            'origin_sale_order',
            'quotation_expected_date',
            'complete_expected_date',
            'delivery_expected_date',
            'installation_expected_date',
            'warranty_service_type',
            'sap_reason_id',
            'status_before_repair',
            'status_after_repair',
            'replace_serial_number',
            'product_status_before',
            'product_status_image_before_ids',
            'product_status_after',
            'product_status_image_after_ids',
            'completed_task_description',
            'survey_type',
            'expected_survey_date',
            'survey_attachment_ids',
            'survey_result_description',
            'consultation_approval_note',
            'require_technical_solution_design',
            'technical_solution_result',
            'materials_supplier',
            'implementer',
            'need_approval',
            'technical_solution_approval_multipliers',
            'project_complexity',
            'io_number',
            'inverter_point',
            'servo_point',
            'plc_point',
            'hmi_point',
            'cabinet_enclosure_point',
            'installation_capacity',
            'quotation_task_result',
            'quotation_task_link',
            'quotation_approval_result',
            'quotation_reject_reason',
            'quotation_reject_reason_other',
            'expected_implementation_date',
            'expected_implementation_address',
            'equipment_attachment_ids',
            'technical_solution_design_attachment_ids',
            'materials_attachment_ids',
            'handover_result',
            'acceptance_result',
            'acceptance_attachment_ids',
            'acceptance_design_attachment_ids',
            'acceptance_report_attachment_ids',
        }
        fields_tracking_changed = fields_tracking & set(vals.keys())
        changed_field_labels = self.env['ir.model.fields'].with_context(lang=self.env.lang).search(
            [('model', '=', 'ticket.helpdesk'), ('name', 'in', list(fields_tracking_changed))]).mapped(
            'field_description')
        # Save changed field labels to context for automation
        self.env.context = dict(self.env.context or {},
                                changed_fields=changed_field_labels)

    def write(self, vals):
        old_status_by_id = {rec.id: rec.status for rec in self}
        self.pass_changed_fields_to_context(vals)
        vals = self.clean_instance_vals(vals)
        result = super(TicketHelpDesk, self).write(vals)
        if not self.env.context.get('skip_ticket_rating_sync') and 'ticket_rating' in vals:
            for rec in self.filtered('ticket_rating'):
                rec.with_context(skip_ticket_rating_sync=True).sudo().write({
                    'customer_rating': str(rec.ticket_rating.rate or 0),
                    'review': rec.ticket_rating.note or '',
                })
        if any(field in vals for field in ('warranty_service_type', 'note_SO')):
            for rec in self:
                document_note = rec._build_document_note()
                # Ghi thẳng vào note của tất cả SO liên quan
                rec.sale_order_ids.sudo().write({'note': document_note})
        if 'io_number' in vals:
            # only tickets with a non-zero io_number will get a category
            to_map = self.filtered(lambda t: t.io_number)
            to_map._apply_io_mapping()
        if 'sap_reason_id' in vals:
            for rec in self:
                reason = rec.sap_reason_id
                reason_id = (
                    reason.id
                    if reason
                    and reason.active
                    and reason.code not in EXCLUDED_SAP_REASON_CODES
                    and reason.voucher_type == rec.sap_voucher_type
                    else False
                )
                rec.sale_order_ids.filtered(
                    lambda so: so.status in ('draft', 'confirmed')
                ).sudo().write({'sap_reason_id': reason_id})
        if 'sap_voucher_type' in vals:
            for rec in self:
                rec.sale_order_ids.filtered(
                    lambda so: so.status in ('draft', 'confirmed')
                ).sudo().write({'sap_voucher_type': rec.sap_voucher_type})
        for rec in self:
            if old_status_by_id.get(rec.id) != 'closed' and rec.status == 'closed':
                rec.sudo()._send_zns_notification(
                    'dat_website_helpdesk.zalo_zns_template_get_customer_feedback',
                    _('ZNS đánh giá sau khi đóng phiếu'),
                )
        return result

    def _send_zns_notification(self, template_xmlid, subject):
        self.ensure_one()
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            self._log_zns_auto_result(subject, _('Không tìm thấy mẫu ZNS %s') % template_xmlid)
            return False

        phone = self.customer_phone
        if not phone:
            self._log_zns_auto_result(subject, _('Không có số điện thoại khách hàng để gửi ZNS.'))
            return False

        existing = self.env['zalo.zns.message'].sudo().search([
            ('helpdesk_ticket_id', '=', self.id),
            ('template_id', '=', template.id),
            ('state', 'in', ('draft', 'sent', 'done')),
        ], limit=1)
        if existing:
            return existing

        try:
            batch = self.env['zalo.zns.batch'].sudo().create({
                'template_id': template.id,
                'origin_model': 'ticket.helpdesk',
            })
            message = self.env['zalo.zns.message'].sudo().create({
                'batch_id': batch.id,
                'template_id': template.id,
                'helpdesk_ticket_id': self.id,
                'phone': phone,
                'name': '%s - %s' % (subject, self.name or self.display_name),
            })
            message.action_send_message_zalo_zns()
            if message.state == 'failed':
                self._log_zns_auto_result(subject, message.error_message or _('Gửi ZNS thất bại.'))
            else:
                self._log_zns_auto_result(subject, _('Đã tạo/gửi ZNS tới số %s.') % phone)
            return message
        except Exception as error:
            _logger.exception("Auto ZNS failed for ticket %s template %s", self.name, template_xmlid)
            self._log_zns_auto_result(subject, error)
            return False

    def _log_zns_auto_result(self, subject, message):
        self.ensure_one()
        try:
            self.message_post(body='<b>%s</b><br/>%s' % (subject, message))
        except Exception:
            _logger.exception("Cannot post ZNS auto result on ticket %s", self.id)

    # ==== Helper: build document note (Loại dịch vụ - Ghi chú SO) ====
    def _build_document_note(self):
        self.ensure_one()
        document_note_parts = []

        # Lấy label của loại dịch vụ (warranty_service_type)
        service_type_label = ""
        if getattr(self, "warranty_service_type", False):
            field = self._fields.get("warranty_service_type")
            if field:
                try:
                    selection = dict(field._description_selection(self.env))
                    service_type_label = selection.get(
                        self.warranty_service_type, self.warranty_service_type
                    )
                except Exception:
                    service_type_label = self.warranty_service_type

        if service_type_label:
            document_note_parts.append(service_type_label)

        # Ghi chú SO trên ticket
        note_so = (self.note_SO or self.delivery_address or "").strip()
        if note_so:
            document_note_parts.append(note_so)

        return " - ".join(document_note_parts)

    def _build_device_document_note(self):
        """Build the serial/product part appended to a quotation document note."""
        self.ensure_one()
        lot = self.stock_lot_id
        product = lot.product_id or self.product_id
        device_note_parts = []

        serial_number = (lot.name or "").strip()
        if serial_number:
            device_note_parts.append(_("Số series: %s") % serial_number)

        device_name = (product.display_name or "").strip()
        if device_name:
            device_note_parts.append(_("Tên thiết bị: %s") % device_name)

        return " - ".join(device_note_parts)

    def _build_quotation_document_note(self, existing_note=None):
        """Append ticket device data without overwriting or duplicating the note."""
        self.ensure_one()
        if existing_note is None:
            existing_note = self._build_document_note()

        existing_note = (existing_note or "").strip()
        device_note = self._build_device_document_note()
        if not device_note or device_note in existing_note:
            return existing_note
        return " - ".join(part for part in (existing_note, device_note) if part)


    def _prepare_sale_order_action_context(self, context=None):
        """Open the quotation in the ticket branch's company context."""
        self.ensure_one()
        context = dict(context or {})
        if not self.branch:
            return context

        user_company_ids = set(self.env.user.company_ids.ids)
        if self.branch.id not in user_company_ids:
            raise UserError(
                _(
                    "Bạn chưa được cấp quyền công ty %s. "
                    "Vui lòng liên hệ quản trị viên để được bổ sung quyền."
                )
                % self.branch.display_name
            )

        allowed_company_ids = list(
            context.get("allowed_company_ids")
            or self.env.context.get("allowed_company_ids")
            or self.env.companies.ids
        )
        context["allowed_company_ids"] = [self.branch.id] + [
            company_id
            for company_id in allowed_company_ids
            if company_id != self.branch.id and company_id in user_company_ids
        ]
        return context

    def action_create_quotation(self):
        self.ensure_one()
        if not (self.owner_id and (self.owner_id.card_code or '').strip()):
            raise UserError(
                _("Khách hàng chưa có mã CardCode! Vui lòng cập nhật CardCode trước khi tạo báo giá.")
            )
    
        product_ids = []
        if self.step_id and self.step_id.id == self.env.ref(self.WORKFLOW_1_STEP_3).id:
            product_ids = self.stock_lot_id.product_id.ids
        elif self.wf_external_id == "workflow_1" and getattr(self, "is_exchange_1_1", False):
            lot = getattr(self, "new_stock_lot_id", False) or self.stock_lot_id
            if lot and lot.product_id:
                product_ids = lot.product_id.ids
    
        address2 = self.owner_address
        default_receiving_address = self.env.ref('dat_website_helpdesk.sale_order_ref_address_2', raise_if_not_found=False)
        if default_receiving_address and default_receiving_address.address:
            address2 = default_receiving_address.address
    
        ctx = self._prepare_sale_order_action_context({
            "default_partner_id": self.owner_id.id,
            "default_phone": self.owner_phone,
            "default_email": self.owner_email,
            "default_street": self.owner_id.street,
            "default_street2": address2,
            "default_city": self.owner_id.city,
            "default_state_id": self.owner_id.state_id.id if self.owner_id.state_id else False,
            "default_zip": self.owner_id.zip,
            "default_country_id": self.owner_id.country_id.id if self.owner_id.country_id else False,
            "default_ticket_id": self.id,
            "default_ticket_name": self.name,
            "default_product_ids": product_ids,
            "default_company_id": self.branch.id,
            "default_assigned_user_id": self.env.user.id,
            "default_document_note": self._build_quotation_document_note(),
            "default_note": self._build_document_note(),
            "default_branch": self.branch.id,
            "default_doc_type": "SO",
            "default_ticket_type": "sell",
            "default_warranty_service_type": self.warranty_service_type,
            "default_sap_voucher_type": self.sap_voucher_type,
            "default_sap_reason_id": (
                self.sap_reason_id.id
                if self.sap_reason_id
                and self.sap_reason_id.active
                and self.sap_reason_id.code not in EXCLUDED_SAP_REASON_CODES
                and self.sap_reason_id.voucher_type == self.sap_voucher_type
                else False
            ),
            "default_sap_so_status": self.sap_so_status if self.sap_so_status else None,
        })
    
        return {
            'type': 'ir.actions.act_window',
            'name': _('Materials'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'current',
            'context': ctx,
        }


    @api.onchange("is_exchange_1_1")
    def _onchange_is_exchange_1_1(self):
        for rec in self:
            if rec.is_exchange_1_1:
                rec.is_return_defective = False
                rec.is_need_new_so = True
            else:
                rec.new_stock_lot_id = False
                rec.new_serial_number = False
                rec.replace_serial_number = False
    
    @api.onchange("is_return_defective")
    def _onchange_is_return_defective(self):
        for rec in self:
            if rec.is_return_defective:
                rec.is_exchange_1_1 = False
                rec.new_stock_lot_id = False
                rec.new_serial_number = False
                rec.replace_serial_number = False
    
    @api.onchange("is_received_defective")
    def _onchange_is_received_defective(self):
        for rec in self:
            if rec.is_received_defective and not rec.received_defective_date:
                rec.received_defective_date = fields.Datetime.now()
            if not rec.is_received_defective:
                rec.received_defective_date = False


    def action_open_quotation(self):
        sale_order_ids = self.sale_order_ids
        if len(sale_order_ids) == 1:
            return {
                'name': _('Sale Order'),
                'res_model': 'sale.order',
                'view_id': False,
                'res_id': sale_order_ids.id,
                'view_mode': 'form',
                'type': 'ir.actions.act_window',
            }
        else:
            return {
                'name': _('Sale Order'),
                'domain': [('ticket_id', '=', self.id)],
                'res_model': 'sale.order',
                'view_id': False,
                'view_mode': 'tree,form',
                'type': 'ir.actions.act_window',
            }

    def action_open_child_ticket(self):
        if not self.child_ids:
            raise UserError(_('This ticket has no parent ticket.'))

        if len(self.child_ids) == 1:
            return {
                'name': _('Tasks'),
                'res_model': 'ticket.helpdesk',
                'view_id': False,
                'res_id': self.child_ids.id,
                'view_mode': 'form',
                'type': 'ir.actions.act_window',
            }
        else:
            return {
                'name': _('Tasks'),
                'domain': [('id', 'in', self.child_ids.ids)],
                'res_model': 'ticket.helpdesk',
                'view_id': False,
                'view_mode': 'tree,form',
                'type': 'ir.actions.act_window',
            }

    def action_send_reply(self):
        """Action to sent reply button"""
        template_id = self.env['ir.config_parameter'].sudo().get_param(
            'dat_website_helpdesk.reply_template_id'
        )
        template_id = self.env['mail.template'].browse(int(template_id))
        if template_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'mail',
                'res_model': 'mail.compose.message',
                'view_mode': 'form',
                'target': 'new',
                'views': [[False, 'form']],
                'context': {
                    'default_model': 'ticket.helpdesk',
                    'default_res_ids': self.ids,
                    'default_template_id': template_id.id
                }
            }
        return {
            'type': 'ir.actions.act_window',
            'name': 'mail',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'views': [[False, 'form']],
            'context': {
                'default_model': 'ticket.helpdesk',
                'default_res_ids': self.ids,
            }
        }

    def action_create_on_site_installation_ticket(self):
        """Create on site installation ticket"""
        ticket_id = self.sudo().env['ticket.helpdesk'].create({
            'customer_id': self.customer_id.id,
            'customer_phone': self.customer_phone,
            'customer_company_name': self.customer_company_name,
            'customer_contact_name': self.customer_contact_name,
            'customer_email': self.customer_email,
            'customer_address': self.customer_address,
            'step_id': self.env.ref(self.WORKFLOW_2_STEP_2).id,
            'workflow_id': self.env.ref(self.WORKFLOW_2).id,
            'priority_id': self.priority_id.id,
            'subject': self.subject,
            'branch': self.branch.id,
            'department_id': self.department_id.id,
            'description': self.description,
            'assigned_user_id': self.assigned_user_id.id,
            'stock_lot_id': self.stock_lot_id.id,
            'service_action': self.service_action,
            'ticket_type_id': self.ticket_type_id.id,
            'state_id': self.state_id.id,
            'owner_id': self.owner_id.id,
            'owner_address': self.owner_address,
            'delivery_address': self.delivery_address,
            'product_error_note': self.product_error_note,
            'ticket_product_image_ids': self.ticket_product_image_ids,
            'quotation_expected_date': self.quotation_expected_date,
            'complete_expected_date': self.complete_expected_date,
            'delivery_expected_date': self.delivery_expected_date,
            'parent_id': self.id
        })
        self._message_log_batch(bodies={self.id: _('Ticket %s has been created') % ticket_id.name})
        return ticket_id

    def action_create_deployment_request_processing_ticket(self):
        """Create Deployment Request Processing ticket"""
        ticket_id = self.sudo().env['ticket.helpdesk'].create({
            'customer_id': self.customer_id.id,
            'customer_phone': self.customer_phone,
            'customer_company_name': self.customer_company_name,
            'customer_contact_name': self.customer_contact_name,
            'customer_email': self.customer_email,
            'customer_address': self.customer_address,
            'step_id': self.env.ref(self.WORKFLOW_4_STEP_2).id,
            'workflow_id': self.env.ref(self.WORKFLOW_4).id,
            'priority_id': self.priority_id.id,
            'subject': self.subject,
            'branch': self.branch.id,
            'department_id': self.department_id.id,
            'description': self.description,
            'ticket_attachment_ids': [(6, 0, self.ticket_attachment_ids.ids)],
            'ticket_note': self.ticket_note,
            'assigned_user_id': self.assigned_user_id.id,
            'ticket_type_id': self.env.ref('dat_website_helpdesk.ticket_type_6').id,
            'state_id': self.state_id.id,
            'owner_id': self.owner_id.id,
            'owner_address': self.owner_address,
            'delivery_address': self.delivery_address,
            'install_attachment_ids': [(6, 0, self.install_attachment_ids.ids)],
            'install_address': self.install_address,
            'install_note': self.install_note,
            'technical_solution_attachment_ids': [(6, 0, self.technical_solution_attachment_ids.ids)],
            'technical_solution_note': self.technical_solution_note,
            'technical_solution_link': self.technical_solution_link,
            'materials_supplier': self.materials_supplier,
            'expected_implementation_date': self.expected_implementation_date,
            'implementation_note': self.implementation_note,
            'inverter_point': self.inverter_point,
            'servo_point': self.servo_point,
            'plc_point': self.plc_point,
            'cabinet_enclosure_point': self.cabinet_enclosure_point,
            'hmi_point': self.hmi_point,
            'quotation_approval_result': self.quotation_approval_result,
            'quotation_reject_reason': self.quotation_reject_reason,
            'quotation_reject_note': self.quotation_reject_note,
            'implementer': self.implementer,
            'implementation_address_reality': self.implementation_address_reality,
            'parent_id': self.id
        })
        self._message_log_batch(bodies={self.id: _('Ticket %s has been created') % ticket_id.name})
        return ticket_id

    
    def action_next_step_wf1_step5a_confirm_replace_and_serial(self):
        self.ensure_one()

        remote = self._wf1_is_remote()
        has_flag = bool(self.is_exchange_1_1 or self.is_return_defective)

        # Không đổi / không trả -> đóng luôn
        if not has_flag:
            step_9_id = self._safe_ref_id(getattr(self, "WORKFLOW_1_STEP_9", ""))
            if step_9_id:
                self.step_id = step_9_id
            else:
                self.status = "closed"
                if hasattr(self, "end_date") and not self.end_date:
                    self.end_date = fields.Datetime.now()
            return True

        # Trả hàng lỗi
        if self.is_return_defective:
            if not remote:
                if not self.is_received_defective:
                    raise ValidationError(_("Trả hàng lỗi: phải xác nhận 'Đã nhận hàng lỗi?' trước khi xử lý tiếp."))
                if hasattr(self, "received_defective_date") and not self.received_defective_date:
                    self.received_defective_date = fields.Datetime.now()

            step_7_id = self._safe_ref_id(getattr(self, "WORKFLOW_1_STEP_7", ""))
            if step_7_id:
                self.step_id = step_7_id
            return True

        # Đổi 1-1
        if self.is_exchange_1_1:
            has_new_serial = bool(getattr(self, "new_stock_lot_id", False)) or bool(getattr(self, "replace_serial_number", False))

            if not remote:
                if not self.is_received_defective:
                    raise ValidationError(_("Đổi 1-1: phải xác nhận 'Đã nhận hàng lỗi?' trước khi xử lý tiếp."))
                if hasattr(self, "received_defective_date") and not self.received_defective_date:
                    self.received_defective_date = fields.Datetime.now()

            self.is_need_new_so = True
            if has_new_serial:
                self._ensure_replace_serial_saved()

            step_7_id = self._safe_ref_id(getattr(self, "WORKFLOW_1_STEP_7", ""))
            if step_7_id:
                self.step_id = step_7_id
            return True

        return True
    
    
    def _safe_ref_id(self, xmlid):
        """Return record id for xmlid, or False if xmlid not found (no crash)."""
        rec = self.env.ref(xmlid, raise_if_not_found=False)
        return rec.id if rec else False


    def _get_steps_actions(self):
        wf1_id = self.env.ref(self.WORKFLOW_1).id
        wf2_id = self.env.ref(self.WORKFLOW_2).id
        wf3_id = self.env.ref(self.WORKFLOW_3).id
        wf4_id = self.env.ref(self.WORKFLOW_4).id
        return_workflow_id = self.env.ref(self.WORKFLOW_RETURN).id

        res = {
            # =====================================================
            # WF1
            # =====================================================
            wf1_id: {
                self.env.ref(self.WORKFLOW_1_STEP_2b).id: self.action_next_step_wf1_step2_receiving,
                self.env.ref(self.WORKFLOW_1_STEP_3).id: self.action_next_step_wf1_step3_repair_quotation,
                self.env.ref(self.WORKFLOW_1_STEP_4).id: self.action_next_step_wf1_step4_material_dispatch,
                self.env.ref(self.WORKFLOW_1_STEP_5).id: self.action_next_step_wf1_step5_repair,
                self.env.ref(self.WORKFLOW_1_STEP_6).id: self.action_next_step_wf1_step6_reassembly_to_original_state,
            },

            # =====================================================
            # WF2
            # =====================================================
            wf2_id: {
                self.env.ref(self.WORKFLOW_2_STEP_2b).id: self.action_next_step_wf2_step2_receiving,
                self.env.ref(self.WORKFLOW_2_STEP_3).id: self.action_next_step_wf2_step3_go_to_location,
                self.env.ref(self.WORKFLOW_2_STEP_4).id: self.action_next_step_wf2_step4_begin_processing,
                self.env.ref(self.WORKFLOW_2_STEP_5).id: self.action_next_step_wf2_step5_installation_completed,
            },

            # =====================================================
            # WF3
            # =====================================================
            wf3_id: {
                self.env.ref(self.WORKFLOW_3_STEP_2b).id: self.action_next_step_wf3_step2_receiving,
                self.env.ref(self.WORKFLOW_3_STEP_3).id: self.action_next_step_wf3_step3_survey_tech_solutions,
                self.env.ref(self.WORKFLOW_3_STEP_4).id: self.action_next_step_wf3_step4_feedback_survey_results,
                self.env.ref(self.WORKFLOW_3_STEP_5).id: self.action_next_step_wf3_step5_approve_survey_results,
                self.env.ref(self.WORKFLOW_3_STEP_6).id: self.action_next_step_wf3_step6_provide_tech_solutions,
                self.env.ref(self.WORKFLOW_3_STEP_7).id: self.action_next_step_wf3_step7_approve_tech_solution,
                self.env.ref(self.WORKFLOW_3_STEP_8).id: self.action_next_step_wf3_step8_prepare_quotation,
                self.env.ref(self.WORKFLOW_3_STEP_9).id: self.action_next_step_wf3_step9_provide_quotation,
            },

            # =====================================================
            # WF4
            # =====================================================
            wf4_id: {
                self.env.ref(self.WORKFLOW_4_STEP_2b).id: self.action_next_step_wf4_step2_receiving,
                self.env.ref(self.WORKFLOW_4_STEP_3).id: self.action_next_step_wf4_step3_plan_deployment,
                self.env.ref(self.WORKFLOW_4_STEP_4).id: self.action_next_step_wf4_step4_receive_equipment_docs,
                self.env.ref(self.WORKFLOW_4_STEP_5).id: self.action_next_step_wf4_step5_deploy_tech_solution_and_handle_errors,
                self.env.ref(self.WORKFLOW_4_STEP_6).id: self.action_next_step_wf4_step6_handover_solution,
                self.env.ref(self.WORKFLOW_4_STEP_7).id: self.action_next_step_wf4_step7_acceptance_completion,
            },
            return_workflow_id: {
                self.env.ref(self.WORKFLOW_RETURN_STEP_COMPLETE).id: self.action_complete_return_ticket,
            },
        }

        # =====================================================
        # OPTIONAL STEPS: add only if XMLID exists (avoid crash)
        # =====================================================

        # WF1 - step 5A (Replace confirm)
        step_5a_id = self._safe_ref_id(getattr(self, "WORKFLOW_1_STEP_5A", ""))
        if step_5a_id:
            res[wf1_id][step_5a_id] = self.action_next_step_wf1_step5a_confirm_replace_and_serial

        # WF1 - step 7 (Product delivery)
        step_7_id = self._safe_ref_id(getattr(self, "WORKFLOW_1_STEP_7", ""))
        if step_7_id:
            res[wf1_id][step_7_id] = self.action_next_step_wf1_step7_product_delivery

        # WF1 - step 8 (Onsite)
        step_8_id = self._safe_ref_id(getattr(self, "WORKFLOW_1_STEP_8", ""))
        if step_8_id and hasattr(self, "action_next_step_wf1_step8_on_site_installation_and_repair"):
            res[wf1_id][step_8_id] = self.action_next_step_wf1_step8_on_site_installation_and_repair


        # WF1 - step 9 (Technical done / close)
        step_9_id = self._safe_ref_id(getattr(self, "WORKFLOW_1_STEP_9", ""))
        if step_9_id:
            res[wf1_id][step_9_id] = self.action_next_step_wf1_step9_technical_done_close

        # WF2 - step 6 (Approval)
        step_wf2_6_id = self._safe_ref_id(getattr(self, "WORKFLOW_2_STEP_6", ""))
        if step_wf2_6_id:
            res[wf2_id][step_wf2_6_id] = self.action_next_step_wf2_step6_approval

        return res

    def action_complete_return_ticket(self):
        self.ensure_one()
        self.status = 'closed'
        if not self.end_date:
            self.end_date = fields.Datetime.now()
        return True

    def action_next_step_wf2_step6_approval(self):
        self.ensure_one()
        # Đây là bước cuối WF2 (Approval). Bạn có thể đóng ticket onsite hoặc set trạng thái hoàn tất.
        # Nếu bạn có field status:
        if hasattr(self, "status"):
            self.status = "closed"
        # Nếu bạn có step "follow up" hoặc "technical done" riêng thì set step_id tương ứng ở đây.
        return True

    def action_next_step_wf1_step9_technical_done_close(self):
        self.ensure_one()
        self.status = "closed"
        if hasattr(self, "end_date") and not self.end_date:
            self.end_date = fields.Datetime.now()
        return True
    def _ensure_exchange_service_so(self):
        """
        Hook tạo SO cho ĐV trong case đổi 1-1.
        - Nếu hệ thống bạn đã có hàm tạo SO ở module khác, hãy implement theo 1 trong các tên bên dưới.
        - Nếu chưa có, hàm này sẽ chặn đóng ticket để tránh "đã close nhưng chưa có SO".
        """
        self.ensure_one()

        # Nếu đã có SO gắn ticket thì OK
        if self.sale_order_ids:
            return True

        # Nếu module khác có hàm tạo SO thì gọi
        for fn in [
            "action_create_exchange_service_so",
            "action_create_exchange_sale_order",
            "_create_exchange_service_so",
            "_create_exchange_sale_order",
        ]:
            if hasattr(self, fn):
                getattr(self, fn)()
                return True

        # Không có hàm tạo SO => chặn để đúng quy trình
        raise ValidationError(_(
            "Đổi 1-1: chưa tạo SO cho ĐV. Vui lòng tạo SO trước khi đóng/giao trả."
        ))


    def _ensure_replace_serial_saved(self):
        """Đảm bảo Replace Serial Number đã được set đúng theo lựa chọn serial mới."""
        self.ensure_one()
        # ưu tiên lot
        if getattr(self, "new_stock_lot_id", False):
            self.replace_serial_number = self.new_stock_lot_id.name
            return True

        # fallback: nếu user nhập replace_serial_number sẵn thì OK
        if self.replace_serial_number:
            return True

        raise ValidationError(_("Đổi 1-1: thiếu Replace Serial Number (serial mới)."))

    def action_next_step_wf1_step7_product_delivery(self):
        self.ensure_one()

        # Nếu có đổi/trả thì khi bấm Next Step ở Step 7 => bắt buộc đã nhận hàng lỗi
        if self.is_exchange_1_1 or self.is_return_defective:
            if not self.is_received_defective:
                raise ValidationError(_("Vui lòng xác nhận 'Đã nhận hàng lỗi?' trước khi kết thúc."))

            if hasattr(self, "received_defective_date") and not self.received_defective_date:
                self.received_defective_date = fields.Datetime.now()

        if self.is_exchange_1_1:
            has_new_serial = bool(getattr(self, "new_stock_lot_id", False)) or bool(getattr(self, "replace_serial_number", False))
            if has_new_serial:
                self._ensure_replace_serial_saved()

            # phải có SO cho ĐV
            self._ensure_exchange_service_so()

        # Pass hết điều kiện -> qua Step 9 để đóng
        step_9_id = self._safe_ref_id(getattr(self, "WORKFLOW_1_STEP_9", ""))
        if step_9_id:
            self.step_id = step_9_id
        else:
            self.status = "closed"
            if hasattr(self, "end_date") and not self.end_date:
                self.end_date = fields.Datetime.now()

        return True


    def action_next_step(self):
        cur_step_ticket_step_assignee_ids = self.ticket_step_assignee_ids.filtered(
            lambda line: line.step_id.id == self.step_id.id)
        cur_user_ticket_step_assignee_ids = cur_step_ticket_step_assignee_ids.filtered(
            lambda line: line.user_id.id == self.env.user.id)
        if not cur_user_ticket_step_assignee_ids.done:
            cur_user_ticket_step_assignee_ids.done = True
        elif not all(cur_step_ticket_step_assignee_ids.mapped('done')):
            raise ValidationError(_('You have already clicked on the next step button.'))

        if not all(cur_step_ticket_step_assignee_ids.mapped('done')):
            return True
        self.ticket_step_assignee_ids = [(2, line.id, 0) for line in cur_step_ticket_step_assignee_ids]
        steps_actions = self._get_steps_actions()
        workflow_id = self.workflow_id.id
        step_id = self.step_id.id if self.step_id else None

        if workflow_id in steps_actions and step_id in steps_actions[workflow_id]:
            steps_actions[workflow_id][step_id]()
            if self.workflow_id.id in (self.env.ref(self.WORKFLOW_3).id, self.env.ref(self.WORKFLOW_4).id):
                if not (self.step_id.id == self.env.ref(
                        self.WORKFLOW_3_STEP_9).id and self.require_technical_solution_design == 'no') and self.next_step_assigned_user_id:
                    self.sudo().write({'assigned_user_id': self.next_step_assigned_user_id.id,
                                       'next_step_assigned_user_id': False}
                                      )

        self._message_log_batch(bodies={self.id: _('Click On "%s"') % _('Next Step')})

    # Steps WF1
    def action_next_step_wf1_step2_receiving(self):
        self.ensure_one()

        # Ngoài BH -> Báo giá + sửa chữa
        if self.product_warranty_status != 'warranty':
            self.is_need_new_so = True
            self.step_id = self.env.ref(self.WORKFLOW_1_STEP_3).id
            self.check_reception = False
            return True

        # Còn BH
        if self.service_action == 'onsite_technical_support':
            self.step_id = self.env.ref(self.WORKFLOW_1_STEP_8).id
            self.workflow_id = self.env.ref(self.WORKFLOW_2).id
            self._create_parent_ticket()
            self.check_reception = False
            return True

        # Nếu cần vật tư -> bắt buộc qua Step 4 (Xuất vật tư)
        if self.require_materials == 'yes':
            self.step_id = self.env.ref(self.WORKFLOW_1_STEP_4).id
            self.check_reception = False
            return True

        # Không cần vật tư -> Step 5A (nếu có), fallback Step 7
        step_5a_id = self._safe_ref_id(getattr(self, "WORKFLOW_1_STEP_5A", ""))
        if step_5a_id:
            self.step_id = step_5a_id
        else:
            step_7_id = self._safe_ref_id(getattr(self, "WORKFLOW_1_STEP_7", ""))
            if step_7_id:
                self.step_id = step_7_id
        self.check_reception = False
        return True


    def action_next_step_wf1_step3_repair_quotation(self):
        if not self.sale_order_ids:
            raise ValidationError(
                _('You must create a sale order and provide feedback before proceeding to the next step.'))
        if not self.sale_order_feedback:
            raise ValidationError(_('You must provide feedback on the sale order before proceeding to the next step.'))
        if self.sale_order_feedback == 'agree':
            self.step_id = self.env.ref(self.WORKFLOW_1_STEP_4)
        else:
            self.step_id = self.env.ref(self.WORKFLOW_1_STEP_6)
            self.reassembly = True

    def action_next_step_wf1_step4_material_dispatch(self):
        self.ensure_one()
    
        _logger.info(
            "[WF1][STEP4][START] ticket_id=%s ticket=%s ticket_type_id=%s ticket_type=%s warranty_status=%s",
            self.id,
            self.name,
            self.ticket_type_id.id if self.ticket_type_id else False,
            self.ticket_type_id.name if self.ticket_type_id else False,
            self.product_warranty_status,
        )
    
        if not self.ticket_type_id:
            _logger.warning(
                "[WF1][STEP4][VALIDATION] ticket=%s missing ticket_type_id",
                self.name,
            )
            raise ValidationError(_('You must select the ticket type before proceeding to the next step.'))

        dxvt_number = (self.sap_dxvt_order_number or '').strip()
        if dxvt_number:
            for order in self.sale_order_ids.filtered(lambda so: so.status == 'confirmed'):
                order._move_dxvt_lines_to_target_warehouse()
            _logger.info(
                "[WF1][STEP4][DXVT][SKIP] ticket=%s sap_dxvt_order_number=%s",
                self.name,
                dxvt_number,
            )
            self._message_log_batch(bodies={
                self.id: _('Ticket đã có ĐXVT %s, bỏ qua tạo ĐXVT và chuyển bước tiếp theo.') % dxvt_number
            })

            if self.ticket_type_id.id == self.env.ref(self.TICKET_TYPE_3).id:
                self.step_id = self.env.ref(self.WORKFLOW_1_STEP_7)
            elif self.ticket_type_id.id == self.env.ref(self.TICKET_TYPE_2).id:
                self.step_id = self.env.ref(self.WORKFLOW_1_STEP_8)
                if not self.child_ids:
                    self.action_create_on_site_installation_ticket()
            elif self.ticket_type_id.id == self.env.ref(self.TICKET_TYPE_1).id:
                self.step_id = self.env.ref(self.WORKFLOW_1_STEP_5)
                self.warranty = True
            return True
    
        domain = [('ticket_id', '=', self.id), ('status', '=', 'confirmed')]
    
        _logger.info(
            "[WF1][STEP4][SEARCH_SO] ticket=%s domain=%s",
            self.name,
            domain,
        )
    
        sale_order = self.env['sale.order'].search(domain, limit=1)
    
        _logger.info(
            "[WF1][STEP4][SEARCH_SO][RESULT] ticket=%s sale_order_id=%s sale_order=%s status=%s",
            self.name,
            sale_order.id if sale_order else False,
            sale_order.name if sale_order else False,
            sale_order.status if sale_order else False,
        )
    
        if sale_order:
            try:
                _logger.info(
                    "[WF1][STEP4][DXVT][BEFORE] ticket=%s sale_order_id=%s sale_order=%s",
                    self.name,
                    sale_order.id,
                    sale_order.name,
                )
    
                doc_number = sale_order.create_sap_doc(doc_type='DXVT')
    
                _logger.info(
                    "[WF1][STEP4][DXVT][AFTER] ticket=%s sale_order=%s doc_number=%s",
                    self.name,
                    sale_order.name,
                    doc_number,
                )
    
                if isinstance(doc_number, (dict, list)):
                    raise ValidationError(
                        _("SAP không trả về số ĐXVT hợp lệ. Response: %s") % doc_number
                    )

                if doc_number:
                    self.sap_dxvt_order_number = doc_number
                    sale_order._move_dxvt_lines_to_target_warehouse()
                    message = _('Đã tạo ĐXVT thành công trên SAP với doc number = %s') % doc_number
                    self._message_log_batch(bodies={self.id: message})
                    self.popup_notification = message
    
                    _logger.info(
                        "[WF1][STEP4][DXVT][SUCCESS] ticket=%s sap_dxvt_order_number=%s popup=%s",
                        self.name,
                        self.sap_dxvt_order_number,
                        self.popup_notification,
                    )
    
            except Exception as e:
                _logger.exception(
                    "[WF1][STEP4][DXVT][ERROR] ticket_id=%s ticket=%s sale_order_id=%s sale_order=%s error=%s",
                    self.id,
                    self.name,
                    sale_order.id if sale_order else False,
                    sale_order.name if sale_order else False,
                    e,
                )
                raise
        else:
            _logger.warning(
                "[WF1][STEP4][NO_SO] ticket=%s no sale order found for domain=%s",
                self.name,
                domain,
            )
            raise ValidationError(
                _('Bạn phải tạo và xác nhận đề xuất vật tư trước khi xuất vật tư.')
            )
    
        if self.ticket_type_id.id == self.env.ref(self.TICKET_TYPE_3).id:
            _logger.info(
                "[WF1][STEP4][NEXT_STEP] ticket=%s -> WORKFLOW_1_STEP_7",
                self.name,
            )
            self.step_id = self.env.ref(self.WORKFLOW_1_STEP_7)
    
        elif self.ticket_type_id.id == self.env.ref(self.TICKET_TYPE_2).id:
            _logger.info(
                "[WF1][STEP4][NEXT_STEP] ticket=%s -> WORKFLOW_1_STEP_8 and create on-site installation ticket",
                self.name,
            )
            self.step_id = self.env.ref(self.WORKFLOW_1_STEP_8)
            self.action_create_on_site_installation_ticket()
    
        elif self.ticket_type_id.id == self.env.ref(self.TICKET_TYPE_1).id:
            _logger.info(
                "[WF1][STEP4][NEXT_STEP] ticket=%s -> WORKFLOW_1_STEP_5 warranty=True",
                self.name,
            )
            self.step_id = self.env.ref(self.WORKFLOW_1_STEP_5)
            self.warranty = True
    
        _logger.info(
            "[WF1][STEP4][END] ticket=%s final_step_id=%s final_step=%s warranty=%s sap_dxvt_order_number=%s",
            self.name,
            self.step_id.id if self.step_id else False,
            self.step_id.name if self.step_id else False,
            self.warranty,
            self.sap_dxvt_order_number,
        )

    def action_next_step_wf1_step5_repair(self):
        if not self.warranty_service_type:
            raise ValidationError(
                _('You must fill in the Repair, Warranty information before proceeding to the next step.'))

        # Only create an SAP SO once. The user may create it manually from the
        # quotation before moving the ticket to the next step.
        if self.product_warranty_status == 'warranty':
            sale_orders = self.env['sale.order'].search([('ticket_id', '=', self.id)])
        else:
            sale_orders = self.env['sale.order'].search([
                ('ticket_id', '=', self.id),
                ('status', '=', 'confirmed'),
            ])

        created_order = sale_orders.filtered(lambda order: (order.sap_status or '').strip())[:1]
        existing_so_number = (self.sap_sale_order_number or '').strip()
        if not existing_so_number and created_order:
            existing_so_number = (created_order.sap_status or '').strip()
            self.sap_sale_order_number = existing_so_number

        sale_order = created_order or sale_orders[:1]

        if existing_so_number:
            self._message_log_batch(bodies={
                self.id: _(
                    'SO SAP %(so_number)s đã tồn tại, bỏ qua gọi tạo lại và chuyển bước tiếp theo.'
                ) % {'so_number': existing_so_number}
            })
        elif sale_order:
            so_number = sale_order.create_sap_doc(doc_type='SO')

            if so_number:
                self.sap_sale_order_number = so_number
                message = _('Đã tạo SO thành công trên SAP với SO number = %s') % so_number
                self._message_log_batch(bodies={self.id: message})
                self.popup_notification = message

        if self.require_on_site_installation == 'yes':
            self.step_id = self.env.ref(self.WORKFLOW_1_STEP_8)
            self.action_create_on_site_installation_ticket()
        else:
            self.step_id = self.env.ref(self.WORKFLOW_1_STEP_7)

    @api.onchange('warranty_service_type')
    def _onchange_warranty_service_type(self):
        for record in self:
            if record.warranty_service_type == 'repair':
                record.replace_serial_number = False
                record.warranty_start_date = False
                record.warranty_end_date = False
            elif record.warranty_service_type == 'replace':
                record.status_before_repair = False
                record.status_after_repair = False
                record.warranty_start_date = record.product_warranty_start_date
                record.warranty_end_date = record.product_warranty_end_date
            else:
                record.status_before_repair = False
                record.status_after_repair = False
                record.replace_serial_number = False
                record.warranty_start_date = False
                record.warranty_end_date = False

    def action_next_step_wf1_step6_reassembly_to_original_state(self):
        self.step_id = self.env.ref(self.WORKFLOW_1_STEP_7)

    # Steps WF2
    def action_next_step_wf2_step2_receiving(self):
        self.step_id = self.env.ref(self.WORKFLOW_2_STEP_3)
        self.check_reception = False

    def action_next_step_wf2_step3_go_to_location(self):
        self.step_id = self.env.ref(self.WORKFLOW_2_STEP_4)
        self.wf2_status_before_flag = True

    def action_next_step_wf2_step4_begin_processing(self):
        self.step_id = self.env.ref(self.WORKFLOW_2_STEP_5)
        self.wf2_status_after_flag = True

    def action_next_step_wf2_step5_installation_completed(self):
        self.step_id = self.env.ref(self.WORKFLOW_2_STEP_6)
        self.sudo().write({'assigned_user_id': self.get_assigned_user_id_based_on_department(
            department=self.department_id, branch=self.branch, ticket_type=self.ticket_type_id).id})

    # Steps WF3
    def action_next_step_wf3_step2_receiving(self):
        self.step_id = self.env.ref(self.WORKFLOW_3_STEP_3)
        self.check_reception = False

    def action_next_step_wf3_step3_survey_tech_solutions(self):
        if self.status == 'on_hold':
            self.action_continue()
        self.step_id = self.env.ref(self.WORKFLOW_3_STEP_4)

    def action_next_step_wf3_step4_feedback_survey_results(self):
        self.step_id = self.env.ref(self.WORKFLOW_3_STEP_5)
        self.sudo().write({'assigned_user_id': self.get_assigned_user_id_based_on_department(
            department=self.department_id, branch=self.branch, ticket_type=self.ticket_type_id).id})

    def action_next_step_wf3_step5_approve_survey_results(self):
        if self.require_technical_solution_design == 'yes':
            self.sudo().write({'step_id': self.env.ref(self.WORKFLOW_3_STEP_6).id})
        elif self.require_technical_solution_design == 'no':
            vals = {
                'step_id': self.env.ref(self.WORKFLOW_3_STEP_9).id,
            }
            if self.sudo().saleperson_id.user_id:
                vals['assigned_user_id'] = self.sudo().saleperson_id.user_id.id
            self.sudo().write(vals)

    def action_next_step_wf3_step6_provide_tech_solutions(self):
        self.is_need_new_so = True
        self.assigned_follower_ids = False
        if self.need_approval == 'yes':
            self.step_id = self.env.ref(self.WORKFLOW_3_STEP_7)
            self.sudo().write(
                {'assigned_user_id': self.get_assigned_user_id_based_on_department(department=self.department_id,
                                                                                   branch=self.branch,
                                                                                   ticket_type=self.ticket_type_id).id})
        elif self.need_approval == 'no':
            self.step_id = self.env.ref(self.WORKFLOW_3_STEP_8)

    def action_next_step_wf3_step7_approve_tech_solution(self):
        self.step_id = self.env.ref(self.WORKFLOW_3_STEP_8)

    def action_next_step_wf3_step8_prepare_quotation(self):
        self.step_id = self.env.ref(self.WORKFLOW_3_STEP_9)
        if self.sudo().saleperson_id.user_id:
            vals = {
                'assigned_user_id': self.sudo().saleperson_id.user_id.id
            }
            self.sudo().write(vals)

    def action_next_step_wf3_step9_provide_quotation(self):
        for ticket in self:
            result = ticket.quotation_approval_result
            if result == 'successful':
                ticket._approve_quotation()
            elif result in ('resurvey', 'change_technical_solution'):
                ticket._request_resurvey_or_change(result)
            elif result == 'rejected':
                ticket._reject_quotation()

    def _approve_quotation(self):
        if self.implementer in ('dat', 'customer'):
            self.action_create_deployment_request_processing_ticket()
        self.status = 'closed'
        self._update_sale_orders('confirmed')

    def _request_resurvey_or_change(self, result):
        if result == 'resurvey':
            step_ref = self.WORKFLOW_3_STEP_3
        else:  # change_technical_solution
            step_ref = self.WORKFLOW_3_STEP_6

        self.sudo().step_id = self.env.ref(step_ref)
        self.sudo().write({
            'quotation_approval_result': False,
            'quotation_reject_reason': False,
            'quotation_reject_note': False,
        })
        self._update_sale_orders('cancelled')

    def _reject_quotation(self):
        self.status = 'rejected'
        self._update_sale_orders('rejected', {
            'reject_reason': self.quotation_reject_reason,
        })

    def _update_sale_orders(self, status, extra_vals=None):
        orders = self.sale_order_ids.filtered(lambda so: so.status == 'draft')
        if not orders:
            return
        vals = {'status': status}
        if extra_vals:
            vals.update(extra_vals)
        orders.sudo().write(vals)

    # Steps WF4
    def action_next_step_wf4_step2_receiving(self):
        if self.implementer == 'dat':
            self.step_id = self.env.ref(self.WORKFLOW_4_STEP_3)
        elif self.implementer == 'customer':
            self.step_id = self.env.ref(self.WORKFLOW_4_STEP_FOLLOW_UP)
        else:
            raise UserError(_("Bạn chỉ có thể chọn đối tượng triển khai là 'DAT' hoặc 'Khách hàng' ở bước này"))
        self.check_action_assign = False
        self.check_reception = False

    def action_next_step_wf4_step3_plan_deployment(self):
        self.status = 'in_progress'
        if self.materials_supplier == 'dat':
            self.step_id = self.env.ref(self.WORKFLOW_4_STEP_4)
        else:
            self.step_id = self.env.ref(self.WORKFLOW_4_STEP_5)
            self._create_tasks_from_templates(self.evaluate_domain)

    def action_next_step_wf4_step4_receive_equipment_docs(self):
        self.step_id = self.env.ref(self.WORKFLOW_4_STEP_5)
        self._create_tasks_from_templates(self.evaluate_domain)

    def _create_tasks_from_templates(self, evaluate_domain):
        template_env = self.env['implementation.work.template']
        work_env = self.env['implementation.work']

        field = 'is_for_automation_dep' if evaluate_domain else 'is_for_energy_dep'
        templates = template_env.search_read(
            [('active', '=', True), (field, '=', True)],
            ['name']
        ) or template_env.search_read([('active', '=', True)], ['name'])
        if not templates:
            return

        vals_list = [{'ticket_id': self.id, 'name': tpl['name'], } for tpl in templates]

        work_env.create(vals_list)

    def action_next_step_wf4_step5_deploy_tech_solution_and_handle_errors(self):
        self.ensure_one()
        if self.evaluate_domain and self.solution_total_point == 0:
            raise UserError(_("Tất cả các điểm cấu hình không được bằng 0!"))
        self._assert_all_works_approved()
        self._assert_all_errors_resolved()
        self.step_id = self.env.ref(self.WORKFLOW_4_STEP_6)

    def _assert_all_works_approved(self):
        missing = self.implementation_work_ids.filtered(
            lambda w: not w.approved or w.approved == 'inprogress'
        )
        if missing:
            names = missing.mapped('name')
            formatted_list = '\n- ' + '\n- '.join(names)
            raise UserError(_(
                "Vui lòng nhập thông tin 'Trạng Thái' thành 'Hoàn thành' hoặc 'Hủy bỏ' cho các công việc:%s"
            ) % formatted_list)

    def _assert_all_errors_resolved(self):
        unresolved = self.implementation_error_ids.filtered(lambda e: e.state != 'done')
        if unresolved:
            raise ValidationError(_(
                "Cannot proceed: all the errors are not yet resolved."
            ))

    def action_next_step_wf4_step6_handover_solution(self):
        self.step_id = self.env.ref(self.WORKFLOW_4_STEP_7)
        self._assert_all_errors_resolved()

    def action_next_step_wf4_step7_acceptance_completion(self):
        if not self.is_project_file_completed:
            raise UserError(_("Please complete the project documentation before pressing the button."))

        self.sudo().write(
            {'assigned_user_id': self.get_assigned_user_id_based_on_department(department=self.department_id,
                                                                               branch=self.branch,
                                                                               ticket_type=self.ticket_type_id).id,
             'assigned_follower_ids': False,
             'need_button_approve': True,
             'next_step_button_invisible': True,
             'next_step_button_name': False})

    def action_open_ticket_reject_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Ticket'),
            'res_model': 'ticket.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ticket_id': self.id,
                'default_reject_reason': self.request_return_reason,
            },
            'views': [[False, 'form']]
        }

    def action_reception(self):
        for rec in self:
            if rec.workflow_id == self.env.ref(self.WORKFLOW_1):
                rec.action_next_step_wf1_step2_receiving()
            elif rec.workflow_id == self.env.ref(self.WORKFLOW_2):
                rec.action_next_step_wf2_step2_receiving()
            elif rec.workflow_id == self.env.ref(self.WORKFLOW_3):
                rec.action_next_step_wf3_step2_receiving()
            else:
                rec.action_next_step_wf4_step2_receiving()
            rec.check_reception = True
            rec.start_date = fields.Datetime.now()
        self._message_log_batch(bodies={self.id: _('Click On "%s"') % _('Reception')})

    def action_open_assign_wizard(self):
        return {
            'name': _('Assign Ticket'),
            'type': 'ir.actions.act_window',
            'res_model': 'ticket.reassign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ticket_id': self.id,
                'assigned_user_id': self.assigned_user_id.id,
                'is_reassign': False,
            }
        }

    def action_assigned(self, new_user_id):
        for rec in self:
            if rec.workflow_id == self.env.ref(self.WORKFLOW_1):
                step_id = self.env.ref(self.WORKFLOW_1_STEP_2b).id
            elif rec.workflow_id == self.env.ref(self.WORKFLOW_2):
                step_id = self.env.ref(self.WORKFLOW_2_STEP_2b).id
            elif rec.workflow_id == self.env.ref(self.WORKFLOW_3):
                step_id = self.env.ref(self.WORKFLOW_3_STEP_2b).id
            elif rec.workflow_id == self.env.ref(self.WORKFLOW_RETURN):
                step_id = self.env.ref(self.WORKFLOW_RETURN_STEP_COMPLETE).id
            else:
                step_id = self.env.ref(self.WORKFLOW_4_STEP_2b).id
            vals = {
                'assigned_user_id': new_user_id.id,
                'step_id': step_id,
                'status': 'in_progress',
                'start_date': fields.Datetime.now(),
                'check_action_assign': True
            }
            if rec.workflow_id == self.env.ref(self.WORKFLOW_4):
                vals['reception_project_code'] = self.get_project_code(rec)
            self.sudo().write(vals)

            self._message_log_batch(bodies={self.id: _('Click On "%s"') % _('Assigned')})

    def get_project_code(self, rec):
        today = fields.Date.context_today(self)
        if isinstance(today, str):
            today_date = fields.Date.from_string(today)
        else:
            today_date = today
        date_str = today_date.strftime("%d_%m_%Y")
        department_code = 'DA_AUTO' if rec.evaluate_domain else 'ENERGY'
        domain = [
            ('reception_project_code', 'like', f"{department_code}_%")
        ]
        last = self.search(domain, order='reception_project_code desc', limit=1)
        if last and last.reception_project_code:
            try:
                last_seq = int(last.reception_project_code.rsplit('_', 1)[-1])
            except (ValueError, IndexError):
                last_seq = 0
        else:
            last_seq = 0

        new_seq = last_seq + 1
        return f"{date_str}_{department_code}_{new_seq:06d}"

    def action_approved(self):
        self.status = 'closed'
        self.end_date = fields.Datetime.now()
        self.approved_by = self.env.user.id
        self.need_button_approve = False
        self.approved_date = fields.Datetime.now()

        self._message_log_batch(bodies={self.id: _('Click On "%s"') % _('Approved')})

    def action_reject(self, reject_reason=False):
        for rec in self:
            rec.status = 'rejected'
            rec.reject_reason = reject_reason
            message = _("This ticket has been rejected by %s. \n", self.env.user.name)
            if rec.reject_reason:
                message += _("Reject Reason: %s", self.reject_reason)
            rec._message_log_batch(bodies={rec.id: message})

    def action_return(self):
        for rec in self:
            rec.status = 'rejected'
            message = _("This ticket has been requested return by %s. \n", self.env.user.name)
            if rec.request_return_reason:
                message += _("Request Return Reason: %s", self.request_return_reason)
            rec._message_log_batch(bodies={rec.id: message})

    def action_hold(self, on_hold_reason=False, next_expected_survey_date=False):
        for rec in self:
            rec.status = 'on_hold'
            rec.on_hold_reason = on_hold_reason
            rec.next_expected_survey_date = next_expected_survey_date
            message = _("This ticket has been set on hold by %s. \n", self.env.user.name)
            if rec.on_hold_reason:
                message += _("On Hold Reason: %s", self.on_hold_reason)
            rec._message_log_batch(bodies={rec.id: message})

    def action_open_on_hold_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('On Hold Ticket'),
            'res_model': 'ticket.on.hold.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ticket_id': self.id,
                'default_on_hold_reason': self.on_hold_reason,
            },
            'views': [[False, 'form']]
        }

    def action_open_return_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Return Step'),
            'res_model': 'ticket.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ticket_id': self.id,
            },
            'views': [[False, 'form']]
        }

    def action_return_step(self, return_step_reason=False):
        for rec in self:
            if rec.step_id == self.env.ref(self.WORKFLOW_3_STEP_5):
                rec.sudo().write({
                    'step_id': self.env.ref(self.WORKFLOW_3_STEP_4).id,
                    'check_is_approved_survey': 'no',
                })
            elif rec.step_id == self.env.ref(self.WORKFLOW_3_STEP_7):
                self.sudo().write({
                    'step_id': self.env.ref(self.WORKFLOW_3_STEP_6).id,
                    'check_is_approved_techical_solution': 'no',
                })
            elif rec.step_id == self.env.ref(self.WORKFLOW_4_STEP_7):
                self.sudo().write({
                    'need_button_approve': False,
                    'project_complexity': False,
                    'is_project_file_completed': False,
                })

    def action_open_reassign_wizard(self):
        return {
            'name': _('Reassign Ticket'),
            'type': 'ir.actions.act_window',
            'res_model': 'ticket.reassign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ticket_id': self.id,
                'assigned_user_id': self.assigned_user_id.id,
                'is_reassign': True,
            }
        }

    def action_reassign(self, new_user_id):
        for rec in self:
            rec.sudo().write({'assigned_user_id': new_user_id.id})

    def action_continue(self):
        self.status = 'in_progress'
        self._message_log_batch(bodies={self.id: _('Click On "%s"') % _('Continue')})

    def action_view_technical_proposals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Technical Proposals',
            'res_model': 'technical.proposal',
            'view_mode': 'tree,form',
            'domain': [('ticket_id', '=', self.id)],
            'context': {'default_ticket_id': self.id},
            'target': 'current',
        }

    def clean_instance_vals(self, vals):
        for key, value in vals.items():
            if value and isinstance(value, datetime):
                dt_utc = value.astimezone(pytz.utc)
                dt_naive = dt_utc.replace(tzinfo=None)
                vals[key] = dt_naive
        return vals

    def clean_vals_list(self, vals_list):
        for vals in vals_list:
            vals = self.clean_instance_vals(vals)
        return vals_list

    # -------------------------------------------------------------------------
    # BnK helpers
    # -------------------------------------------------------------------------
    def _bnk_build_payload(self):
        """
        Body cho 4 API BnK:

        {
            "DocNum": "HCM-2505-00015",   # Ticket ID
            "CardCode": "C016984",        # Mã khách hàng
            "CardName": "CÔNG TY ...",    # Tên khách
            "ItemNo": "SG40CX-P2",        # Mã sản phẩm
            "ItemName": "Inverter ...",   # Tên sản phẩm
            "SerialNumber": "xxxx",       # Serial
            "bplid": 1                    # Chi nhánh 1/2/3
        }
        """
        self.ensure_one()

        # --- DocNum: Ticket ID ---
        docnum = self.name
        if not docnum:
            raise UserError(_("Ticket chưa có Ticket ID."))

        # --- Khách hàng: từ customer_id ---
        partner = self.customer_id
        if not partner:
            raise UserError(_("Vui lòng chọn Khách hàng trước khi gọi BnK."))

        card_code = partner.card_code or partner.ref
        card_name = partner.name or ""
        if not card_code:
            raise UserError(_("Khách hàng chưa có mã CardCode (card_code/ref)."))

        # --- Serial & sản phẩm: từ stock_lot_id ---
        lot = self.stock_lot_id
        if not lot:
            raise UserError(_("Vui lòng chọn Serial Number (stock_lot_id)."))

        serial = lot.name or ""
        product = lot.product_id
        if not product:
            raise UserError(_("Serial chưa gắn với sản phẩm."))

        item_no = product.default_code or product.name
        item_name = product.name or ""
        if not item_no:
            raise UserError(_("Sản phẩm chưa có mã (default_code)."))

        # --- Chi nhánh / bplid ---
        # ưu tiên lấy từ branch, nếu không có thì đọc system parameter
        company = self.branch or self.env.company
        bplid = getattr(company, "bplid", False)
        if not bplid:
            ICP = self.env["ir.config_parameter"].sudo()
            bplid_str = (ICP.get_param("dat_bnk.default_bplid") or "1").strip()
            try:
                bplid = int(bplid_str)
            except ValueError:
                bplid = 1

        return {
            "DocNum": docnum,
            "CardCode": card_code,
            "CardName": card_name,
            "ItemNo": item_no,
            "ItemName": item_name,
            "SerialNumber": serial,
            "bplid": bplid,
        }

    def _bnk_call_api(self, api_link):
        """
        Gọi POST tới BnK và chỉ báo thành công khi body API xác nhận thành công.
        """
        self.ensure_one()

        operation = 'bnk:%s' % api_link
        operation_names = {
            '/NhapKhoTiepNhanBH': _('Nhập kho tiếp nhận bảo hành'),
            '/ChuyenVaoKhoService': _('Chuyển vào kho Service'),
            '/ChuyenVaoKhoHangLoiDaDoiBaoHanh': _('Chuyển vào kho hàng lỗi đã đổi bảo hành'),
            '/XuatKhoiKhoTiepNhanBH': _('Xuất khỏi kho tiếp nhận bảo hành'),
            '/NhapKhoTiepNhanBHLT': _('Nhập kho tiếp nhận bảo hành (LT)'),
            '/ChuyenVaoKhoServiceLT': _('Chuyển vào kho Service (LT)'),
            '/ChuyenVaoKhoHangLoiDaDoiBaoHanhLT': _('Chuyển vào kho hàng lỗi đã đổi bảo hành (LT)'),
            '/XuatKhoiKhoTiepNhanBHLT': _('Xuất khỏi kho tiếp nhận bảo hành (LT)'),
        }
        operation_name = operation_names.get(api_link, api_link)
        confirmation = self._external_document_confirmation_action(operation, operation_name)
        if confirmation:
            return confirmation

        ICP = self.env["ir.config_parameter"].sudo()

        # ---- Base URL ----
        api_base_url = (ICP.get_param("dat_bnk.bnk_api_url") or "").strip()
        if not api_base_url:
            api_base_url = "https://api-dat.datgroup.com.vn/BnK"
        api_base_url = api_base_url.rstrip("/")

        url = f"{api_base_url}{api_link}"

        # ---- Headers từ config (SAP headers được tái sử dụng) ----
        try:
            headers = dict(self._get_sap_headers_safe() or {})
        except Exception as e:
            _logger.error("Không parse SAP headers: %s", e)
            headers = {}

        # Đảm bảo có Content-Type
        headers.setdefault("Content-Type", "application/json")

        payload = self._bnk_build_payload()

        # ---- LOG REQUEST ----
        _logger.info(
            "BnK request: url=%s, headers(no-secret)=%s, payload=%s",
            url,
            {k: ("***" if k.lower() in ("authorization", "api-key", "x-api-key") else v)
             for k, v in headers.items()},
            json.dumps(payload, ensure_ascii=False),
        )

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
        except Exception as e:
            _logger.exception("Lỗi khi gọi BnK API %s: %s", api_link, e)
            raise UserError(_("Không kết nối được tới BnK (%s): %s") % (api_link, e))

        # ---- LOG RESPONSE ----
        _logger.info(
            "BnK response: url=%s, http_status=%s, text=%s",
            url,
            response.status_code,
            response.text,
        )

        if response.status_code != 200:
            debug_json = {
                "request": payload,
                "response_text": response.text,
            }
            raise UserError(
                _("Gọi BnK thất bại (HTTP %(code)s): %(body)s")
                % {
                    "code": response.status_code,
                    "body": json.dumps(debug_json, ensure_ascii=False),
                }
            )

        try:
            response_json = response.json() if response.text else {}
        except ValueError:
            response_json = {}

        is_success, api_message = self._bnk_parse_api_result(response_json, response.text)
        debug_json = {
            "request": payload,
            "response": response_json or response.text,
        }
        if not is_success:
            raise UserError(
                _("BnK chưa cập nhật thành công: %(message)s\nChi tiết: %(detail)s")
                % {
                    "message": api_message or _("API không trả về trạng thái thành công."),
                    "detail": json.dumps(debug_json, ensure_ascii=False),
                }
            )

        document_number = self._external_document_number_from_response(response_json)
        self._record_external_document(
            operation,
            operation_name,
            document_number=document_number,
            response=response_json or response.text,
        )

        self.write({
            'bnk_warehouse_side': 'lt' if api_link.rstrip('/').upper().endswith('LT') else 'main',
            'bnk_last_api': api_link,
            'bnk_last_success_at': fields.Datetime.now(),
        })

        self._message_log_batch(bodies={
            self.id: _("BnK %(api)s cập nhật thành công. Phản hồi: %(response)s") % {
                "api": api_link,
                "response": json.dumps(response_json or response.text, ensure_ascii=False),
            }
        })

        # ---- Thành công: trả thông báo ----
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Thành công",
                "message": api_message or "BnK cập nhật thành công!",
                "type": "success",
                "sticky": False,
            },
        }

    def _bnk_call_api_sequence(self, api_links):
        self.ensure_one()
        messages = []
        for api_link in api_links:
            action = self._bnk_call_api(api_link)
            params = action.get("params", {}) if isinstance(action, dict) else {}
            messages.append("%s: %s" % (api_link, params.get("message") or _("Thành công")))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Thành công"),
                "message": "\n".join(messages),
                "type": "success",
                "sticky": False,
            },
        }

    def _bnk_parse_api_result(self, response_json, response_text):
        if not response_json:
            text = (response_text or "").strip()
            if text.lower() in ("ok", "success", "true"):
                return True, text
            return False, text or _("API BnK trả về rỗng.")

        status_value = None
        for key in ("status", "success", "isSuccess", "is_success", "resultStatus"):
            if key in response_json:
                status_value = response_json.get(key)
                break

        message = (
            response_json.get("msg")
            or response_json.get("message")
            or response_json.get("error")
            or response_json.get("errorMessage")
            or response_json.get("description")
            or ""
        )

        if isinstance(status_value, bool):
            return status_value, message

        if status_value is not None:
            normalized_status = str(status_value).strip().lower()
            if normalized_status in ("true", "success", "succeeded", "ok", "200", "1"):
                return True, message
            if normalized_status in ("false", "fail", "failed", "error", "0"):
                return False, message

        error_code = response_json.get("errorCode", response_json.get("error_code"))
        if error_code not in (None, "", 0, "0"):
            return False, message or _("API BnK trả về mã lỗi %s.") % error_code

        if response_json.get("docnumber") or response_json.get("DocNum"):
            return True, message

        result = response_json.get("result")
        if isinstance(result, dict):
            result_status = result.get("status") or result.get("success")
            if isinstance(result_status, bool):
                return result_status, message
            if str(result_status or "").strip().lower() in ("true", "success", "succeeded", "ok", "200", "1"):
                return True, message

        return False, message or _("API BnK không trả về status/success hợp lệ.")

    def _get_sap_headers_safe(self):
        """Lấy header SAP, tránh lỗi khi model/method chưa sẵn."""
        try:
            return self.env["res.config.settings"].get_sap_headers()
        except Exception as e:
            _logger.error("Không lấy được SAP headers: %s", e)
            raise UserError(
                _(
                    "Không lấy được thông tin kết nối SAP (headers). "
                    "Vui lòng kiểm tra cấu hình SAP."
                )
            )


    # -------------------------------------------------------------------------
    # 4 ACTION: gọi 4 API BnK
    # -------------------------------------------------------------------------
    def action_bnk_nhap_kho_tiep_nhan_bh(self):
        """
        Nhập kho tiếp nhận bảo hành
        POST /BnK/NhapKhoTiepNhanBH
        """
        return self._bnk_call_api("/NhapKhoTiepNhanBH")

    def action_bnk_chuyen_vao_kho_service(self):
        """
        Chuyển vào kho Service
        POST /BnK/ChuyenVaoKhoService
        """
        # BnK handles the reception-stock removal inside this transfer.
        return self._bnk_call_api("/ChuyenVaoKhoService")

    def action_bnk_chuyen_vao_kho_hang_loi_da_doi_bh(self):
        """
        Chuyển vào kho hàng lỗi đã đổi bảo hành
        POST /BnK/ChuyenVaoKhoHangLoiDaDoiBaoHanh
        """
        return self._bnk_call_api("/ChuyenVaoKhoHangLoiDaDoiBaoHanh")

    def action_bnk_xuat_khoi_kho_tiep_nhan_bh(self):
        """
        Xuất khỏi kho tiếp nhận bảo hành
        POST /BnK/XuatKhoiKhoTiepNhanBH
        """
        return self._bnk_call_api("/XuatKhoiKhoTiepNhanBH")

    def action_bnk_nhap_kho_tiep_nhan_bh_lt(self):
        """
        Nhập kho tiếp nhận bảo hành (LT)
        POST /BnK/NhapKhoTiepNhanBHLT
        """
        return self._bnk_call_api("/NhapKhoTiepNhanBHLT")
    
    def action_bnk_chuyen_vao_kho_service_lt(self):
        """
        Chuyển vào kho Service (LT)
        POST /BnK/ChuyenVaoKhoServiceLT
        """
        return self._bnk_call_api("/ChuyenVaoKhoServiceLT")
    
    def action_bnk_chuyen_vao_kho_hang_loi_da_doi_bh_lt(self):
        """
        Chuyển vào kho hàng lỗi đã đổi bảo hành (LT)
        POST /BnK/ChuyenVaoKhoHangLoiDaDoiBaoHanhLT
        """
        return self._bnk_call_api("/ChuyenVaoKhoHangLoiDaDoiBaoHanhLT")
    
    def action_bnk_xuat_khoi_kho_tiep_nhan_bh_lt(self):
        """
        Xuất khỏi kho tiếp nhận bảo hành (LT)
        POST /BnK/XuatKhoiKhoTiepNhanBHLT
        """
        return self._bnk_call_api("/XuatKhoiKhoTiepNhanBHLT")
