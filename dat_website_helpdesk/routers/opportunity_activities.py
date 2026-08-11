from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query
from odoo.addons.base.models.res_users import Users
from odoo.addons.core_fastapi.dependencies import authorize_session, format_query
from odoo.addons.core_fastapi.routers.base import BaseModelAPI
from odoo.addons.core_fastapi.schemas import OrderBy
from odoo.addons.core_fastapi.utils.common import get_list_api_response
from odoo.addons.fastapi.dependencies import paging
from odoo.addons.fastapi.schemas import PagedCollection, Paging
from odoo.http import request
from odoo.osv import expression

from ..schemas import (
    OpportunityActivity,
    OpportunityActivityCreate,
)

router = APIRouter()


class OpportunityActivityAPI(BaseModelAPI):
    _model_name = 'dat.opportunity.activity'
    _schema_list = OpportunityActivity
    _schema_item = OpportunityActivity

    @classmethod
    def get_list_search_domain(cls, q: str):
        return [('contents', 'ilike', q)]

    @classmethod
    def get_list_domain(cls, **kwargs):
        domain = []
        q = kwargs.get('q', None)
        opty_code = kwargs.get('opty_code', None)
        opty_id = kwargs.get('opty_id', None)
        date_start = kwargs.get('date_start', None)
        date_end = kwargs.get('date_end', None)

        if q:
            domain = expression.AND([domain, cls.get_list_search_domain(q)])
        if opty_code:
            domain = expression.AND([domain, [('opty_code', '=', opty_code)]])
        if opty_id:
            domain = expression.AND([domain, [('opty_id', '=', opty_id)]])
        if date_start:
            domain = expression.AND(
                [domain, [('dat_create_date', '>=', date_start)]])
        if date_end:
            domain = expression.AND(
                [domain, [('dat_create_date', '<=', date_end)]])

        return domain

    @classmethod
    async def get_list(
        cls,
        current_user: Annotated[Users | None, Depends(authorize_session)],
        paging: Annotated[Paging, Depends(paging)],
        q: Annotated[str, Depends(format_query)] = None,
        date_start: date = None,
        date_end: date = None,
        opty_code: str = None,
        opty_id: str = None,
        order_by: OrderBy = None,
        sort_by: Annotated[list[str] | None, Query()] = None,
    ):
        domain = cls.get_list_domain(
            q=q,
            date_start=date_start,
            date_end=date_end,
            opty_code=opty_code,
            opty_id=opty_id)
        records, count = get_list_api_response(
            model=cls._model_name,
            domain=domain,
            paging=paging,
            sort_by=sort_by,
            order_by=order_by,
        )
        return PagedCollection[cls._schema_list](
            count=count,
            items=records
        )

    @classmethod
    async def create(
        cls,
        current_user: Annotated[Users | None, Depends(authorize_session)],
        body: Annotated[OpportunityActivityCreate, Form(
            media_type="multipart/form-data")] = None,
    ):
        return cls.create_opportunity_activity(body)

    @classmethod
    def create_opportunity_activity(cls, body: OpportunityActivityCreate):
        cleaned_input = cls.clean_opportunity_activity_creation_input(body)
        new_record = request.env[cls._model_name].create(
            cleaned_input)
        return new_record

    @classmethod
    def clean_opportunity_activity_creation_input(cls, body: OpportunityActivityCreate):
        attachment_model = request.env['ir.attachment']
        ir_attachment_vals_list = attachment_model.extract_attachment_vals_from_pydantic(
            body.attachment_ids)
        attachments = attachment_model.create(ir_attachment_vals_list)

        opty_id = request.env['dat.opportunity'].search(
            [('opty_code', '=', body.opty_code)], limit=1)
        return {
            'attachment_ids': [(6, 0, attachments.ids)],
            'opty_id': opty_id.id,
            **body.model_dump(exclude_unset=True, exclude={'attachment_ids'})
        }


# Define the API routes
router.get(
    "/",
    summary='Get List Of Opportunities',
    response_model=PagedCollection[OpportunityActivity])(
    OpportunityActivityAPI.get_list)

router.post(
    "/",
    summary='Create New Opportunity Activity',
    response_model=OpportunityActivity)(
    OpportunityActivityAPI.create)
