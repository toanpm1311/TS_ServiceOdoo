import json
from datetime import datetime
from enum import Enum
from typing import Annotated, List

from fastapi import APIRouter, Body, Depends, Form, Query
from odoo import _, fields
from odoo.addons.base.models.res_users import Users
from odoo.addons.core_fastapi.dependencies import authorize_session, format_query
from odoo.addons.core_fastapi.routers.base import BaseModelAPI
from odoo.addons.core_fastapi.schemas import MasterData, OrderBy
from odoo.addons.core_fastapi.utils.common import get_list_api_response, get_masterdata
from odoo.addons.fastapi.dependencies import paging
from odoo.addons.fastapi.schemas import PagedCollection, Paging
from odoo.exceptions import UserError
from odoo.http import request
from odoo.osv import expression

from ..schemas import (
    PriorityCode,
    TicketError,
    TicketHelpdesk,
    TicketHelpdeskBase,
    TicketHelpdeskCreate,
    TicketHelpdeskReject,
    TicketHelpdeskStatusDetail,
    TicketHelpdeskAssign,
    TicketHelpdeskUpdate,
    TicketHelpdeskUpdateGeneral,
    TicketHelpdeskUpdateImplementationWork,
    TicketHelpdeskUpdateWF2Step2,
    TicketHelpdeskUpdateWF2Step3,
    TicketHelpdeskUpdateWF2Step4,
    TicketHelpdeskUpdateWF2Step5,
    TicketHelpdeskUpdateWF2Step6,
    TicketHelpdeskUpdateWF4Step2,
    TicketHelpdeskUpdateWF4Step3,
    TicketHelpdeskUpdateWF4Step4,
    TicketHelpdeskUpdateWF4Step5,
    TicketHelpdeskUpdateWF4Step6,
    TicketHelpdeskUpdateWF4Step7,
    TicketMasterData,
    TicketMasterDataSearch,
    TicketStatus,
    TicketImplementer,
    TicketMaterialsSupplier,
    TicketWorkflowCode,
)
from ..utils import ticket as ticket_utils

router = APIRouter()


class TicketAPI(BaseModelAPI):
    _model_name = 'ticket.helpdesk'
    _schema_list = TicketHelpdeskBase
    _schema_item = TicketHelpdesk

    @classmethod
    def get_list_domain(cls, **kwargs):
        domain = []
        q = kwargs.get('q', None)
        wf = kwargs.get('wf', None)
        create_start = kwargs.get('create_start', None)
        create_end = kwargs.get('create_end', None)
        status = kwargs.get('status', None)
        priority_code = kwargs.get('priority_code', None)
        assigned_me = kwargs.get('assigned_me', None)

        if q:
            domain = expression.AND(
                [domain, ['|', ('name', 'ilike', q), ('subject', 'ilike', q)]])
        if wf:
            domain = expression.AND(
                [domain, [('wf_external_id', 'in', wf)]])
        if create_start:
            create_start = datetime.fromtimestamp(create_start)
            domain = expression.AND(
                [domain, [('create_date', '>=', create_start)]])
        if create_end:
            create_end = datetime.fromtimestamp(create_end)
            domain = expression.AND(
                [domain, [('create_date', '<=', create_end)]])
        if status:
            domain = expression.AND(
                [domain, [('status', 'in', [s.name for s in status])]])
        if priority_code:
            domain = expression.AND(
                [domain, [('priority_id.code', 'in', priority_code)]])
        if assigned_me:
            domain = expression.AND(
                [domain, [('assigned_user_id', '=', request.env.user.id)]])

        return domain

    @classmethod
    def update_ticket(cls, id: str, body: TicketHelpdeskUpdate):
        record = request.env[cls._model_name].validate_by_uuid(id)
        implementation_work_ids = body.implementation_work_ids
        if isinstance(implementation_work_ids, str):
            implementation_work_ids = json.loads(implementation_work_ids)
        if implementation_work_ids:
            for work in implementation_work_ids:
                work = TicketHelpdeskUpdateImplementationWork(**work)
                work_object = request.env['implementation.work'].validate_by_uuid(
                    work.uuid)
                work_object.write(work.model_dump(
                    exclude_unset=True, exclude={'uuid'}))
        cleaned_input = cls.clean_update_input(record, body)
        record.write(cleaned_input)
        return record

    @classmethod
    def clean_update_input(cls, ticket, body: TicketHelpdeskUpdate):
        cls.validate_update_input(ticket, body)
        updated_data = body.model_dump(exclude_unset=True, exclude={
            'implementation_work_ids'})
        for k, v in updated_data.items():
            if isinstance(v, Enum):
                updated_data[k] = v.name

        relation_fields_identify = {
            'state_id': 'code',
            'priority_id': 'code',
            'customer_id': 'card_code',
            'saleperson_id': 'sap_hr_code',
            'assigned_user_id': 'uuid',
        }
        results = {}
        for f_name in relation_fields_identify.keys() & updated_data.keys():
            f_object = request.env[cls._model_name]._fields[f_name]
            if isinstance(f_object, fields.Many2one):
                record = request.env[f_object.comodel_name].search(
                    [(relation_fields_identify[f_name], '=', updated_data[f_name])], limit=1)
                results[f_name] = record.id
            elif isinstance(f_object, (fields.One2many, fields.Many2many)):
                records = request.env[f_object.comodel_name].search(
                    [(relation_fields_identify[f_name], '=', updated_data[f_name])])
                results[f_name] = [(6, 0, records.ids)]

        attachment_model = request.env['ir.attachment']
        for f_name in updated_data.keys():
            f_model = request.env[cls._model_name]._fields[f_name].comodel_name
            if f_model == 'ir.attachment':
                attachment_vals_list = attachment_model.extract_attachment_vals_from_pydantic(
                    updated_data[f_name])
                getattr(ticket, f_name).unlink()
                results[f_name] = [(0, 0, vals)
                                   for vals in attachment_vals_list]

        remaining_data = {
            k: v for k, v in updated_data.items() if k not in results.keys()
        }
        results.update(remaining_data)
        return results

    @classmethod
    def get_schema_allowed_in_update_input(cls, ticket):
        """
        Get schemas to be used for updates, following the workflow and the current step.
        """
        step = ticket.step_id
        ticket_model = request.env[cls._model_name]
        schema_allowed = None
        if ticket.workflow_id.id == request.env.ref(ticket_model.WORKFLOW_2).id:
            if step.id in [request.env.ref(ticket_model.WORKFLOW_2_STEP_2).id,
                           request.env.ref(ticket_model.WORKFLOW_2_STEP_2b).id]:
                schema_allowed = TicketHelpdeskUpdateWF2Step2
            elif step.id == request.env.ref(ticket_model.WORKFLOW_2_STEP_3).id:
                schema_allowed = TicketHelpdeskUpdateWF2Step3
            elif step.id == request.env.ref(ticket_model.WORKFLOW_2_STEP_4).id:
                schema_allowed = TicketHelpdeskUpdateWF2Step4
            elif step.id == request.env.ref(ticket_model.WORKFLOW_2_STEP_5).id:
                schema_allowed = TicketHelpdeskUpdateWF2Step5
            elif step.id == request.env.ref(ticket_model.WORKFLOW_2_STEP_6).id:
                schema_allowed = TicketHelpdeskUpdateWF2Step6

        if ticket.workflow_id.id == request.env.ref(ticket_model.WORKFLOW_4).id:
            if step.id in [request.env.ref(ticket_model.WORKFLOW_4_STEP_2).id,
                           request.env.ref(ticket_model.WORKFLOW_4_STEP_2b).id]:
                schema_allowed = TicketHelpdeskUpdateWF4Step2
            elif step.id == request.env.ref(ticket_model.WORKFLOW_4_STEP_3).id:
                schema_allowed = TicketHelpdeskUpdateWF4Step3
            elif step.id == request.env.ref(ticket_model.WORKFLOW_4_STEP_4).id:
                schema_allowed = TicketHelpdeskUpdateWF4Step4
            elif step.id == request.env.ref(ticket_model.WORKFLOW_4_STEP_5).id:
                schema_allowed = TicketHelpdeskUpdateWF4Step5
            elif step.id == request.env.ref(ticket_model.WORKFLOW_4_STEP_6).id:
                schema_allowed = TicketHelpdeskUpdateWF4Step6
            elif step.id == request.env.ref(ticket_model.WORKFLOW_4_STEP_7).id:
                schema_allowed = TicketHelpdeskUpdateWF4Step7

        return schema_allowed

    @classmethod
    def validate_update_input(cls, ticket, body: TicketHelpdeskUpdate):
        schema_allowed = cls.get_schema_allowed_in_update_input(ticket)
        if not schema_allowed:
            raise ValueError(_('You can not update this ticket.'))

        fields_not_allowed = body.model_fields_set - \
                             set(TicketHelpdeskUpdateGeneral.model_fields.keys()) - \
                             set(schema_allowed.model_fields.keys())
        if fields_not_allowed:
            raise UserError(_('You can not update these fields in this step: %s') % ', '.join(
                fields_not_allowed))

    @classmethod
    async def get_list(
            cls,
            current_user: Annotated[Users | None, Depends(authorize_session)],
            paging: Annotated[Paging, Depends(paging)],
            q: Annotated[str, Depends(format_query)] = None,
            order_by: OrderBy = None,
            sort_by: Annotated[list[str] | None, Query()] = None,
            # filter,
            assigned_me: bool = False,
            priority_code: Annotated[list[PriorityCode] | None, Query()] = [],
            status: Annotated[list[TicketStatus] | None, Query()] = [],
            wf: Annotated[list[TicketWorkflowCode] | None, Query()] = [],
            create_start: int = None,
            create_end: int = None,
    ):
        """
        This function retrieves a paginated list of helpdesk tickets, allowing for filtering by various criteria such as search query, creation date range, status, and priority, as well as sorting.

        ### Parameters:

        *   `q: str`
            *   An optional search string. If provided, tickets will be filtered where the 'name' field is like `q`. This parameter is dependency-injected and formatted.
        *   `order_by: str`
            *   An optional enum (`asc` or `desc`) specifying the sort order.
        *   `sort_by: list[str]`
            *   An optional list of field names to sort the results by.
        *   `priority_code: list[str]`
            *   An optional list of `PriorityCode` enums to filter tickets by their priority (e.g., `normal`, `high`).
        *   `status: list[str]`
            *   An optional list of `TicketStatus` enums to filter tickets by their status (e.g., `new`, `in_progress`).
        *   `create_start: int`
            *   An optional Unix timestamp representing the start of the creation date range for filtering.
        *   `create_end: int`
            *   An optional Unix timestamp representing the end of the creation date range for filtering.
        *   `assigned_me: bool`
            *   An optional for filtering whether tickets assigned to the current user or not.

        ### Return:
        *   An object containing:
            *   `count`: The total number of tickets matching the filter criteria.
            *   `items`: A list of `TicketHelpdeskBase` schema objects for the current page.
        """
        domain = cls.get_list_domain(
            q=q,
            wf=wf,
            assigned_me=assigned_me,
            priority_code=priority_code,
            status=status,
            create_end=create_end,
            create_start=create_start)
        records, count = get_list_api_response(
            model=cls._model_name,
            domain=domain,
            paging=paging,
            sort_by=sort_by,
            order_by=order_by,
        )
        return PagedCollection[TicketHelpdesk](
            count=count,
            items=records
        )

    @classmethod
    async def create(
            cls,
            current_user: Annotated[Users | None, Depends(authorize_session)],
            body: Annotated[TicketHelpdeskCreate, Form(
                media_type="multipart/form-data")] = None,
    ):
        new_record = ticket_utils.create_ticket(body)
        return new_record

    @classmethod
    async def update(
            cls,
            current_user: Annotated[Users | None, Depends(authorize_session)],
            id: str,
            body: Annotated[TicketHelpdeskUpdate, Form(
                media_type="multipart/form-data")] = None,
    ):
        return cls.update_ticket(id, body)

    @classmethod
    async def next_step(
            cls,
            current_user: Annotated[Users | None, Depends(authorize_session)],
            id: str,
            body: Annotated[TicketHelpdeskUpdate, Form(
                media_type="multipart/form-data")] = None,
    ):
        record = cls.update_ticket(id, body)
        record.action_next_step()
        return record

    @classmethod
    async def recept_ticket(
            cls,
            current_user: Annotated[Users | None, Depends(authorize_session)],
            id: str,
            body: Annotated[TicketHelpdeskUpdate, Form(
                media_type="multipart/form-data")] = None,
    ):
        record = cls.update_ticket(id, body)
        record.action_reception()
        return record

    @classmethod
    async def assign_ticket(
            cls,
            current_user: Annotated[Users | None, Depends(authorize_session)],
            id: str,
            body: Annotated[TicketHelpdeskAssign, Body()],
    ):
        record = request.env[cls._model_name].validate_by_uuid(id)
        assigned_user = request.env['res.users'].validate_by_uuid(body.assigned_user_id)
        record.action_assigned(assigned_user)
        return record

    @classmethod
    async def reject_ticket(
            cls,
            current_user: Annotated[Users | None, Depends(authorize_session)],
            id: str,
            body: Annotated[TicketHelpdeskReject, Body()],
    ):
        record = request.env[cls._model_name].validate_by_uuid(id)
        record.action_reject(body.reject_reason)
        return record

    @classmethod
    async def get_ticket_status(cls, current_user: Annotated[Users | None, Depends(authorize_session)], id: str):
        ticket = request.env[cls._model_name].validate_by_uuid(id)
        return {
            'status': ticket.status,
            'label': dict(ticket._fields['status'].selection).get(ticket.status),
        }

    @classmethod
    async def get_ticket_errors(cls, current_user: Annotated[Users | None, Depends(authorize_session)], id: str):
        ticket = request.env[cls._model_name].validate_by_uuid(id)
        return ticket.implementation_error_ids

    @classmethod
    async def get_ticket_masterdata(
            cls,
            paging: Annotated[Paging, Depends(paging)],
            current_user: Annotated[Users | None, Depends(authorize_session)],
            master_field: TicketMasterData,
            search_field: TicketMasterDataSearch = TicketMasterDataSearch.name,
            ticket_id: str = None,
            q: Annotated[str, Depends(format_query)] = None,
    ):
        """
        Get master data for the ticket creating or update screen.
        Params:
        - master_field: name of ticket master data field
        - search_field: name of field needed to search
        """
        odoo_model = request.env[cls._model_name]
        if master_field == TicketMasterData.activity:
            odoo_model = request.env['ticket.helpdesk.error']
        ticket_field = odoo_model._fields[master_field.name]
        if ticket_field.type == 'selection':
            # For selection fields, we return the selection values directly
            all_records = [
                {'value': name, 'key': code}
                for code, name in ticket_field._description_selection(request.env)
            ]
            if q:
                records = [r for r in all_records if q.lower() in r['value'].lower()]
            else:
                records = all_records
            return PagedCollection[dict](
                count=len(all_records),
                items=records
            )

        model_name = odoo_model[master_field.name]._name
        domain = [(search_field.name, 'ilike', q)] if q else []
        if ticket_id:
            # masterdata for update
            ticket = request.env[cls._model_name].validate_by_uuid(ticket_id)
            if master_field == TicketMasterData.user_id:
                domain.extend([('employee_ids.department_id', '=', ticket.department_id.id),
                               ('company_ids', '=', ticket.branch.id)])
        if master_field == TicketMasterData.state_id:
            domain.append(('country_id', '=', request.env.ref('base.vn').id))
        key_field, value_field = ticket_utils.get_ticket_masterdata_response_field(
            master_field)
        records, total = get_masterdata(
            model_name, key_field, value_field, paging.limit, paging.offset, domain)
        return PagedCollection[dict](
            count=total,
            items=records
        )


# Define the API routes
router.get(
    "/",
    summary='Get List Of Tickets',
    response_model=PagedCollection[TicketHelpdeskBase])(
    TicketAPI.get_list)

router.get(
    "/masterdata",
    summary='Get Ticket Masterdata',
    response_model=PagedCollection[MasterData])(
    TicketAPI.get_ticket_masterdata)

router.get(
    "/{id}",
    summary='Get Ticket Details',
    response_model=TicketHelpdesk)(
    TicketAPI.get)

router.get(
    "/{id}/status",
    summary='Get Ticket Status',
    response_model=TicketHelpdeskStatusDetail)(
    TicketAPI.get_ticket_status)

router.get(
    "/{id}/errors",
    summary='Get Ticket Errors',
    response_model=List[TicketError])(
    TicketAPI.get_ticket_errors)

router.post(
    "/",
    summary='Create New Ticket',
    response_model=TicketHelpdesk)(
    TicketAPI.create)

router.put(
    "/{id}",
    summary='Update Ticket',
    response_model=TicketHelpdesk)(
    TicketAPI.update)

router.post(
    "/{id}/next-step",
    summary='Go To Next Step Of Ticket',
    response_model=TicketHelpdesk)(
    TicketAPI.next_step)

router.post(
    "/{id}/recept",
    summary='Recept Ticket',
    response_model=TicketHelpdesk)(
    TicketAPI.recept_ticket)

router.post(
    "/{id}/assign",
    summary='Assign Ticket',
    response_model=TicketHelpdesk)(
    TicketAPI.assign_ticket)

router.post(
    "/{id}/reject",
    summary='Reject Ticket',
    response_model=TicketHelpdesk)(
    TicketAPI.reject_ticket)
