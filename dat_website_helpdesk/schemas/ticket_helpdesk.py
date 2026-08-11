from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from fastapi import File, UploadFile
from odoo.addons.core_fastapi.schemas import Attachment, BaseModel, BaseORM
from pydantic import Field


class PriorityCode(str, Enum):
    normal = 'normal'
    high = 'high'
    urgent = 'urgent'


class TicketStatus(str, Enum):
    new = 'new'
    in_progress = 'in_progress'
    closed = 'closed'
    rejected = 'rejected'
    on_hold = 'on_hold'


class TicketStepStatusStatus(str, Enum):
    not_started = 'not_started'
    in_progress = 'in_progress'
    on_hold = 'on_hold'
    done = 'done'
    rejected = 'rejected'


class TicketCreateSource(str, Enum):
    dat = 'dat'
    mobile = 'mobile'


class TicketMaterialsSupplier(str, Enum):
    dat = 'dat'
    customer = 'customer'


class TicketImplementer(str, Enum):
    dat = 'dat'
    customer = 'customer'


class TicketMasterData(str, Enum):
    branch = 'branch'
    department_id = 'department'
    customer_id = 'customer'
    user_id = 'user'
    ticket_type_id = 'ticket_type'
    state_id = 'state'
    product_id = 'product'
    step_id = 'step'
    service_action = 'service_action'
    activity = 'activity'
    implementer = 'implementer'
    materials_supplier = 'materials_supplier'


class TicketMasterDataSearch(str, Enum):
    name = 'name'


class YesNoSelection(str, Enum):
    yes = 'yes'
    no = 'no'


class YesNoNASelection(str, Enum):
    yes = 'yes'
    no = 'no'
    na = 'na'


class TicketSurveyType(str, Enum):
    online = 'online'
    offline = 'offline'


class TicketConsultationApprovalResult(str, Enum):
    approve = 'approve'
    reject = 'reject'


class TicketWarrantyServiceType(str, Enum):
    repair = 'repair'
    replace = 'replace'
    replace_with_new_board = 'replace_with_new_board'
    replace_with_old_board = 'replace_with_old_board'
    clean_and_load_test = 'clean_and_load_test'


class TicketWorkflowCode(str, Enum):
    workflow_1 = 'workflow_1'
    workflow_2 = 'workflow_2'
    workflow_3 = 'workflow_3'
    workflow_4 = 'workflow_4'


class State(BaseORM):
    uuid: Optional[str | bool] = Field(default=None)
    name: Optional[str | bool] = Field(default=None)


class Branch(BaseORM):
    uuid: Optional[str | bool] = Field(default=None)
    name: Optional[str | bool] = Field(default=None)


class Customer(BaseORM):
    uuid: Optional[str | bool] = Field(default=None)
    name: Optional[str | bool] = Field(default=None)
    phone: Optional[str | bool] = Field(default=None)
    email: Optional[str | bool] = Field(default=None)
    address: Optional[str | bool] = Field(default=None)


class User(BaseORM):
    uuid: Optional[str | bool] = Field(default=None)
    name: Optional[str | bool] = Field(default=None)


class TicketType(BaseORM):
    uuid: Optional[str | bool] = Field(default=None)
    name: Optional[str | bool] = Field(default=None)


class TicketSerial(BaseORM):
    name: Optional[str | bool] = Field(default=None)
    product_name: Optional[str | bool] = Field(default=None)


class TicketDepartment(BaseORM):
    name: Optional[str | bool] = Field(default=None)
    product_name: Optional[str | bool] = Field(default=None)


class TicketHelpdeskImplementationWork(BaseORM):
    uuid: str
    name: Optional[str | bool] = Field(default=None)
    approved: Optional[str | bool] = Field(default=None)
    note: Optional[str | bool] = Field(default=None)
    start_date: Optional[datetime | bool] = Field(default=None)
    end_date: Optional[datetime | bool] = Field(default=None)


class TicketPriority(BaseORM):
    code: Optional[str | bool] = Field(default=None)
    name: Optional[str | bool] = Field(default=None)
    default: Optional[bool] = Field(default=None)


class TicketWorkflow(BaseORM):
    active: Optional[bool] = Field(default=None)
    name: Optional[str | bool] = Field(default=None)
    code: Optional[str | bool] = Field(default=None)


class TicketStep(BaseORM):
    active: Optional[bool] = Field(default=None)
    name: Optional[str | bool] = Field(default=None)
    code: Optional[str | bool] = Field(default=None)
    sequence: Optional[int | bool] = Field(default=None)
    closing_step: Optional[bool] = Field(default=None)


class TicketHelpdeskBase(BaseORM):
    uuid: Optional[str | bool] = Field(default=None)
    priority_id: Optional[TicketPriority | bool] = Field(default=None)
    name: Optional[str | bool] = Field(default=None)
    subject: Optional[str | bool] = Field(default=None)
    status: Optional[str | bool] = Field(default=None)
    customer_id: Optional[Customer | bool] = Field(default=None)
    ticket_type_id: Optional[TicketType | bool] = Field(default=None)
    delivery_address: Optional[str | bool] = Field(default=None)
    start_date: Optional[datetime | bool] = Field(default=None)
    deadline: Optional[datetime | bool] = Field(default=None)
    create_date: Optional[datetime | bool] = Field(default=None)
    assigned_user_id: Optional[User | bool] = Field(default=None)


class TicketHelpdesk(TicketHelpdeskBase):
    stock_lot_id: Optional[TicketSerial | bool] = Field(
        description='Serial Number', default=None)
    workflow_id: Optional[TicketWorkflow | bool] = Field(default=None)
    step_id: Optional[TicketStep | bool] = Field(default=None)
    wf_external_id: Optional[str | bool] = Field(default=None)
    last_step_status: Optional[str | bool] = Field(default=None)
    description: Optional[str | bool] = Field(default=None)
    reject_reason: Optional[str | bool] = Field(default=None)
    department_name: Optional[str | bool] = Field(default=None)
    origin_sale_order: Optional[str | bool] = Field(default=None)
    install_address: Optional[str | bool] = Field(default=None)
    service_action: Optional[str | bool] = Field(default=None)
    install_address: Optional[str | bool] = Field(default=None)
    installation_expected_date: Optional[date | bool] = Field(default=None)
    lat_move_start: Optional[float | bool] = Field(default=None)
    lng_move_start: Optional[float | bool] = Field(default=None)
    addr_move_start: Optional[str | bool] = Field(default=None)
    lat_move_end: Optional[float | bool] = Field(default=None)
    lng_move_end: Optional[float | bool] = Field(default=None)
    addr_move_end: Optional[str | bool] = Field(default=None)
    branch: Optional[Branch | bool] = Field(default=None)
    state_id: Optional[State | bool] = Field(default=None)

    customer_code: Optional[str | bool] = Field(default=None)
    customer_contact_name: Optional[str | bool] = Field(default=None)
    customer_company_name: Optional[str | bool] = Field(default=None)
    customer_phone: Optional[str | bool] = Field(default=None)
    customer_email: Optional[str | bool] = Field(default=None)
    customer_address: Optional[str | bool] = Field(default=None)

    product_status_before: Optional[str | bool] = Field(
        description='Used for WF2', default=None)
    product_status_after: Optional[str | bool] = Field(
        description='Used for WF2', default=None)
    note_before: Optional[str | bool] = Field(
        description='Used for WF2', default=None)
    note_after: Optional[str | bool] = Field(
        description='Used for WF2', default=None)
    product_status_image_before_ids: Optional[list[Attachment] | bool] = Field(
        description='Used for WF2', default=None)
    product_status_image_after_ids: Optional[list[Attachment] | bool] = Field(
        description='Used for WF2', default=None)

    assigned_follower_ids: Optional[list[User] | bool] = Field(
        description='Used for WF4', default=None)
    expect_appointment_date: Optional[datetime | bool] = Field(
        description='Used for WF4', default=None)
    appointment_note: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    materials_supplier: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    implementation_work_ids: Optional[list[TicketHelpdeskImplementationWork] | bool] = Field(
        description='Used for WF4', default=None)
    handover_result: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    handover_attachment_ids: Optional[list[Attachment] | bool] = Field(
        description='Used for WF4', default=None)
    handover_note: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    acceptance_result: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    acceptance_note: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    acceptance_hsda_attachment_ids: Optional[list[Attachment] | bool] = Field(
        description='Used for WF4', default=None)
    acceptance_attachment_ids: Optional[list[Attachment] | bool] = Field(
        description='Used for WF4', default=None)
    acceptance_design_attachment_ids: Optional[list[Attachment] | bool] = Field(
        description='Used for WF4', default=None)
    acceptance_report_attachment_ids: Optional[list[Attachment] | bool] = Field(
        description='Used for WF4', default=None)
    acceptance_quotation_attachment_ids: Optional[list[Attachment] | bool] = Field(
        description='Used for WF4', default=None)
    ticket_attachment_ids: Optional[list[Attachment] | bool] = Field(
        description='Used for WF4', default=None)
    ticket_note: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    technical_solution_design_attachment_ids: Optional[list[Attachment] | bool] = Field(
        description='Used for WF4', default=None)
    materials_attachment_ids: Optional[list[Attachment] | bool] = Field(
        description='Used for WF4', default=None)
    equipment_attachment_ids: Optional[list[Attachment] | bool] = Field(
        description='Used for WF4', default=None)
    expected_implementation_date: Optional[datetime | bool] = Field(
        description='Used for WF4', default=None)
    confirm_expected_implementation_date: Optional[bool] = Field(
        description='Used for WF4', default=None)
    expected_implementation_address: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    implementation_note: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    reception_note: Optional[str | bool] = Field(
        description='Reception Note in WF4', default=None)
    reception_project_code: Optional[str | bool] = Field(
        description='Project Code in WF4', default=None)
    reception_project_link: Optional[str | bool] = Field(
        description='Project Link in WF4', default=None)
    technical_solution_result: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    technical_solution_attachment_ids: Optional[list[Attachment] | bool] = Field(
        description='Used for WF4', default=None)
    technical_solution_note: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    technical_solution_link: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    materials_supplier: Optional[str | bool] = Field(
        description='Used for WF4. Required in WF4',
        default=None)
    implementer: Optional[str | bool] = Field(
        description='Used for WF4. Required in WF4', default=None)
    implementation_address_reality: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    delivery_solution_address: Optional[str | bool] = Field(
        description='Used for WF4', default=None)
    io_number: Optional[float | bool] = Field(
        description='I/O number in WF4', default=None)
    inverter_point: Optional[float | bool] = Field(
        description='inverter Point in WF4', default=None)
    servo_point: Optional[float | bool] = Field(
        description='Servo Point in WF4', default=None)
    plc_point: Optional[float | bool] = Field(
        description='Plc Point in WF4', default=None)
    hmi_point: Optional[float | bool] = Field(
        description='Hmi Point in WF4', default=None)
    cabinet_enclosure_point: Optional[float | bool] = Field(
        description='Cabinet Point in WF4', default=None)
    solution_total_point: Optional[float | bool] = Field(
        description='Solution Point in WF4', default=None)
    solution_total_point_with_complexity: Optional[float | bool] = Field(
        description='Solution Point With Complexity in WF4', default=None)
    acceptance_project_revenue: Optional[float | bool] = Field(
        description='Project Revenue in WF4', default=None)
    acceptance_dvkt_revenue: Optional[float | bool] = Field(
        description='Technical Service Revenue in WF4', default=None)
    total_error_days: Optional[int | bool] = Field(default=None)
    project_complexity: Optional[str | bool] = Field(
        description='Project Complexity WF4', default=None)
    installation_capacity: Optional[float | bool] = Field(
        description='Installation Capacity in WF4', default=None)
    is_project_file_completed: Optional[bool] = Field(
        description='Is Project File Completed in WF4', default=None)


class TicketHelpdeskCreate(BaseModel):
    # general
    create_source: TicketCreateSource = Field(
        description='Used for all WF')
    subject: str = Field(
        description='Used for all WF')
    branch_id: str = Field(
        description='Used for all WF')
    priority_code: PriorityCode = Field(
        description='Used for all WF')
    department_id: str = Field(
        description='Used for all WF')
    ticket_type_id: str = Field(
        description='Used for all WF')
    customer_card_code: str = Field(
        description='Used for all WF')
    customer_phone: str = Field(
        description='Used for all WF')
    state_code: str = Field(
        description='Used for all WF')
    delivery_address: str = Field(
        description='Used for all WF')
    description: str = Field(
        description='Used for all WF', default=None)

    # wf1
    serial_number: str = Field(
        title='Serial Number',
        description='Used for WF1', default=None)
    product_error_note: str = Field(
        description='Used for WF1', default=None)
    ticket_product_image_ids: List[UploadFile] = File(
        description='Used for WF1', default=None)

    # wf2
    origin_sale_order: str = Field(
        description='Used for WF2', default=None)

    # wf 2,3,4
    install_attachment_ids: List[UploadFile] = File(
        description='Used for WF2, WF3, WF4', default=None)
    install_note: str = Field(
        description='Used for WF2, WF3, WF4', default=None)
    install_address: str = Field(
        description='Used for WF2, WF3, WF4. Required if ticket_type_id is "Install a new product"',
        default=None)

    # wf4
    technical_solution_attachment_ids: List[UploadFile] = File(
        description='Used for WF4', default=None)
    technical_solution_note: str = Field(
        description='Used for WF4', default=None)
    technical_solution_link: str = Field(
        description='Used for WF4', default=None)
    materials_supplier: TicketMaterialsSupplier = Field(
        description='Used for WF4. Required in WF4',
        default=None)
    expected_implementation_date: datetime = Field(
        description='Used for WF4.',
        default=None)
    confirm_expected_implementation_date: bool = Field(
        description='Used for WF4.',
        default=None)
    expected_implementation_address: str = Field(
        description='Used for WF4.',
        default=None)
    implementation_note: str = Field(
        description='Used for WF4', default=None)


class TicketHelpdeskStatusDetail(BaseModel):
    status: str
    label: str


class TicketHelpdeskUpdateLocationStart(BaseModel):
    lat_move_start: float = Field(default=None)
    lng_move_start: float = Field(default=None)
    addr_move_start: str = Field(default=None)


class TicketHelpdeskUpdateLocationEnd(BaseModel):
    lat_move_end: float = Field(default=None)
    lng_move_end: float = Field(default=None)
    addr_move_end: str = Field(default=None)


class TicketHelpdeskUpdateWF2Step2(TicketHelpdeskUpdateLocationStart):
    # Step 2: Assign
    priority_id: PriorityCode = Field(alias='priority_code', default=None)  # required
    service_action: str = Field(default=None)  # required if status != 'new'
    request_return_reason: str = Field(default=None)  # required if service_action == 'request_return'
    assigned_user_id: str = Field(default=None)  # required
    state_id: str = Field(alias='state_code', default=None)
    delivery_address: str = Field(default=None)
    subject: str = Field(default=None)  # required
    description: str = Field(default=None)  # required
    # # Requester Information
    customer_id: str = Field(alias='customer_card_code', default=None)  # required
    customer_contact_name: str = Field(default=None)  # required
    customer_company_name: str = Field(default=None)
    customer_phone: str = Field(default=None)  # required
    customer_email: str = Field(default=None)
    customer_address: str = Field(default=None)
    # # Sale Person Info
    saleperson_id: str = Field(alias='saleperson_code', default=None)
    # # Estimated Appointment Time
    installation_expected_date: datetime = Field(
        default=None,
        ge=datetime.now())


class TicketHelpdeskUpdateWF2Step3(TicketHelpdeskUpdateLocationEnd):
    # Step 3: Go to location (Nothing to edit)
    pass


class TicketHelpdeskUpdateWF2Step4(BaseModel):
    # Step 4: Begin processing
    # # Information Before Processing
    product_status_before: str = Field(default=None)  # required
    note_before: str = Field(default=None)
    product_status_image_before_ids: List[UploadFile] = File(default=None)  # required


class TicketHelpdeskUpdateWF2Step5(TicketHelpdeskUpdateWF2Step4):
    # Step 5: Installation completed
    # # Information After Processing
    product_status_after: str = Field(default=None)  # required
    note_after: str = Field(default=None)
    product_status_image_after_ids: List[UploadFile] = File(default=None)  # required


class TicketHelpdeskUpdateWF2Step6(TicketHelpdeskUpdateWF2Step5):
    # Step 6: Approval
    pass


class TicketHelpdeskUpdateWF2(
    TicketHelpdeskUpdateWF2Step2,
    TicketHelpdeskUpdateWF2Step3,
    TicketHelpdeskUpdateWF2Step6):
    # WF2
    pass


class TicketHelpdeskUpdateWF4Step2ImplementationInfo(BaseModel):
    # # Implementation Info 
    expected_implementation_date: datetime = Field(default=None)  # required
    confirm_expected_implementation_date: bool = Field(default=None)
    expected_implementation_address: str = Field(default=None)
    implementation_note: str = Field(default=None)


class TicketHelpdeskUpdateWF4Step2TechnicalSolutionInfo(BaseModel):
    # # Technical Solution Info
    technical_solution_result: str = Field(default=None)
    technical_solution_attachment_ids: List[UploadFile] = File(default=None)
    technical_solution_note: str = Field(default=None)
    technical_solution_link: str = Field(default=None)
    implementation_address_reality: str = Field(default=None)
    delivery_solution_address: str = Field(default=None)


class TicketHelpdeskUpdateWF4Step2(TicketHelpdeskUpdateWF4Step2ImplementationInfo,
                                   TicketHelpdeskUpdateWF4Step2TechnicalSolutionInfo):
    # Step 2: Assign
    subject: str = Field(default=None)
    description: str = Field(default=None)
    assigned_user_id: str = Field(default=None)
    assigned_follower_ids: list[str] = Field(default=None)
    ticket_attachment_ids: List[UploadFile] = File(default=None)
    ticket_note: str = Field(default=None)
    # # Sale Person Info
    saleperson_id: str = Field(alias='saleperson_code', default=None)
    # # Reception Info
    reception_note: str = Field(default=None)
    reception_project_link: str = Field(default=None)
    # # Requester Information
    customer_id: str = Field(alias='customer_card_code', default=None)  # required
    customer_contact_name: str = Field(default=None)  # required
    customer_company_name: str = Field(default=None)
    customer_phone: str = Field(default=None)  # required
    customer_email: str = Field(default=None)
    customer_address: str = Field(default=None)
    # # Technical Solution Info additional
    materials_supplier: TicketMaterialsSupplier = Field(
        description='Used for WF4. Required in WF4',
        default=None)
    implementer: TicketImplementer = Field(
        description='Used for WF4. Required in WF4', default=None)


class TicketHelpdeskUpdateWF4Step3(TicketHelpdeskUpdateWF4Step2ImplementationInfo,
                                   TicketHelpdeskUpdateWF4Step2TechnicalSolutionInfo):
    assigned_follower_ids: list[str] = Field(default=None)
    reception_note: str = Field(default=None)
    reception_project_link: str = Field(default=None)


class TicketHelpdeskUpdateWF4Step4(TicketHelpdeskUpdateWF4Step3):
    # Step 4: Receive equipment/technical solution documents and materials
    # # Equipment
    equipment_attachment_ids: List[UploadFile] = File(default=None)  # required
    technical_solution_design_attachment_ids: List[UploadFile] = File(default=None)  # required
    materials_attachment_ids: List[UploadFile] = File(default=None)  # required


class TicketHelpdeskUpdateImplementationWork(BaseModel):
    uuid: str
    name: Optional[str | bool] = Field(default=None)
    approved: Optional[YesNoNASelection | bool] = Field(default=None)
    note: Optional[str | bool] = Field(default=None)
    start_date: Optional[datetime | bool] = Field(default=None)
    end_date: Optional[datetime | bool] = Field(default=None)


class TicketHelpdeskUpdateWF4Step5(TicketHelpdeskUpdateWF4Step3):
    # Step 5: DAT deploys and operates the technical solution
    # # Implementation Technical Solution
    implementation_work_ids: Optional[TicketHelpdeskUpdateImplementationWork | str] = Field(
        alias='implementation_works',
        default=None)  # required
    implementation_work_note: str = Field(default=None)
    # # Errors
    # # Evaluate
    io_number: float = Field(default=None)
    inverter_point: float = Field(default=None)
    servo_point: float = Field(default=None)
    plc_point: float = Field(default=None)
    hmi_point: float = Field(default=None)
    cabinet_enclosure_point: float = Field(default=None)
    solution_total_point: float = Field(default=None)
    installation_capacity: float = Field(default=None)


class TicketHelpdeskUpdateWF4Step6(TicketHelpdeskUpdateWF4Step3):
    # Step 6: Hand over the solution to the customer
    # # Handover
    handover_result: str = Field(default=None)  # required
    handover_attachment_ids: List[UploadFile] = File(default=None)
    handover_note: str = Field(default=None)


class TicketHelpdeskUpdateWF4Step7(TicketHelpdeskUpdateWF4Step3):
    # Step 7: Acceptance and completion of project documentation
    # # Acceptance
    acceptance_result: str = Field(default=None)  # required
    is_project_file_completed: bool = Field(default=None)  # required
    acceptance_note: str = Field(default=None)
    acceptance_attachment_ids: List[UploadFile] = File(default=None)  # required
    project_complexity: str = Field(default=None)  # required if evaluate_domain and implementation_point_ids
    acceptance_hsda_attachment_ids: List[UploadFile] = File(default=None)  # required
    acceptance_design_attachment_ids: List[UploadFile] = File(default=None)  # required
    acceptance_report_attachment_ids: List[UploadFile] = File(default=None)
    acceptance_quotation_attachment_ids: List[UploadFile] = File(default=None)
    acceptance_project_revenue: float = Field(default=None)
    acceptance_dvkt_revenue: float = Field(default=None)


class TicketHelpdeskUpdateWF4(
    TicketHelpdeskUpdateWF4Step2,
    TicketHelpdeskUpdateWF4Step4,
    TicketHelpdeskUpdateWF4Step5,
    TicketHelpdeskUpdateWF4Step6,
    TicketHelpdeskUpdateWF4Step7,
):
    # WF4
    pass


class TicketHelpdeskUpdateGeneral(BaseModel):
    # General
    status: TicketStatus = Field(default=None)
    last_step_status: TicketStepStatusStatus = Field(default=None)


class TicketHelpdeskUpdate(
    TicketHelpdeskUpdateGeneral,
    TicketHelpdeskUpdateWF2,
    TicketHelpdeskUpdateWF4,
):
    pass


class TicketHelpdeskAssign(BaseModel):
    assigned_user_id: str


class TicketHelpdeskReject(BaseModel):
    reject_reason: str
