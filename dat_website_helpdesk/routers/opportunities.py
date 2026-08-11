from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from odoo import _
from odoo.addons.base.models.res_users import Users
from odoo.addons.core_fastapi.dependencies import authorize_session, format_query
from odoo.addons.core_fastapi.routers.base import BaseModelAPI
from odoo.addons.fastapi.schemas import PagedCollection
from odoo.http import request
from odoo.osv import expression

from ..schemas import (
    Opportunity,
    OpportunityActivity,
    OpportunityUpdate,
)

router = APIRouter()


class OpportunityAPI(BaseModelAPI):
    _model_name = 'dat.opportunity'
    _schema_list = Opportunity
    _schema_item = Opportunity

    @classmethod
    def get_list_search_domain(cls, q: str):
        return ['|', ('contact_name', 'ilike', q), '|', ('opty_code', 'ilike', q), '|', ('card_name', 'ilike', q), ('card_code', 'ilike', q)]

    @classmethod
    async def get(cls, current_user: Annotated[Users | None, Depends(authorize_session)], opty_id: str):
        return request.env[cls._model_name].search(
            ['|', ('opty_code', '=', opty_id), ('opty_id', '=', opty_id)], limit=1)

    @classmethod
    async def create(cls, current_user: Annotated[Users | None, Depends(authorize_session)], body: Annotated[Opportunity, Body()] = None):
        new_record = request.env[cls._model_name].create(
            body.model_dump(exclude_unset=True))
        return new_record

    @classmethod
    async def update(cls, current_user: Annotated[Users | None, Depends(authorize_session)], opty_id: str, body: Annotated[OpportunityUpdate, Body()] = None):
        record = request.env[cls._model_name].search(
            ['|', ('opty_code', '=', opty_id), ('opty_id', '=', opty_id)])
        record.write(body.model_dump(exclude_unset=True))
        return record

    @classmethod
    async def delete(cls, current_user: Annotated[Users | None, Depends(authorize_session)], opty_id: str):
        request.env[cls._model_name].search(
            ['|', ('opty_code', '=', opty_id), ('opty_id', '=', opty_id)]).unlink()
        return {'detail': _('Delete record successfully.')}

    @classmethod
    async def get_opportunity_activities(
        cls,
        opty_id: str,
        current_user: Annotated[Users | None, Depends(authorize_session)],
        q: Annotated[str, Depends(format_query)] = None,
        date_start: date = None,
        date_end: date = None,
    ):
        domain = ['|', ('opty_id.opty_code', '=', opty_id), ('opty_id.opty_id', '=', opty_id)]
        if q:
            domain = expression.AND([domain, [('contents', 'ilike', q)]])
        if date_start:
            domain = expression.AND(
                [domain, [('dat_create_date', '>=', date_start)]])
        if date_end:
            domain = expression.AND(
                [domain, [('dat_create_date', '<=', date_end)]])
        records = request.env['dat.opportunity.activity'].search(domain)
        return records


# Define the API routes
router.get(
    "/",
    summary='Get List Of Opportunities',
    response_model=PagedCollection[Opportunity])(
    OpportunityAPI.get_list)

router.get(
    "/{opty_id}",
    summary='Get Opportunity Details',
    response_model=Opportunity)(
    OpportunityAPI.get)

router.get(
    "/{opty_id}/activities",
    summary='Get Opportunity Activities',
    response_model=list[OpportunityActivity])(
    OpportunityAPI.get_opportunity_activities)

router.post(
    "/",
    summary='Create New Opportunity',
    response_model=Opportunity)(
    OpportunityAPI.create)

router.put(
    "/{opty_id}",
    summary='Update Opportunity',
    response_model=Opportunity)(
    OpportunityAPI.update)

router.delete(
    "/{opty_id}",
    summary='Delete Opportunity')(
    OpportunityAPI.delete)
