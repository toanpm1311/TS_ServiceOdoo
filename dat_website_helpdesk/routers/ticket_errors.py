from typing import Annotated

from fastapi import APIRouter, Depends, Form
from odoo import _
from odoo.addons.base.models.res_users import Users
from odoo.addons.core_fastapi.dependencies import authorize_session
from odoo.addons.core_fastapi.routers.base import BaseModelAPI
from odoo.exceptions import AccessError
from odoo.http import request

from ..schemas import (
    TicketError,
    TicketErrorCreate,
    TicketErrorUpdate,
)

router = APIRouter()


class TicketErrorAPI(BaseModelAPI):
    _model_name = 'ticket.helpdesk.error'
    _schema_list = TicketError
    _schema_item = TicketError

    @classmethod
    def _extract_user(cls, value):
        record = request.env['res.users'].validate_by_uuid(value)
        return record.id

    @classmethod
    def validate_permission(cls, ticket):
        if any([
            request.env.uid != ticket.assigned_user_id.id,
            ticket.status in ['rejected', 'closed', 'on_hold']
        ]):
            raise AccessError(_('Permission Denied'))

    @classmethod
    def clean_update_and_creation_input(cls, body, odoo_object=None):
        ticket = None
        if odoo_object:
            ticket = odoo_object.ticket_id
        elif body.ticket_id:
            ticket = request.env['ticket.helpdesk'].validate_by_uuid(
                body.ticket_id)
        cls.validate_permission(ticket)

        result = super().clean_update_and_creation_input(body, odoo_object)
        if 'detected_by' in result:
            result['detected_by'] = cls._extract_user(result['detected_by'])
        if 'ticket_id' in result:
            result['ticket_id'] = ticket.id
        if 'activity' in result:
            result['activity'] = request.env['implementation.work.template'].validate_by_uuid(
                result['activity']).id

        return result

    @classmethod
    async def create(
        cls,
        current_user: Annotated[Users | None, Depends(authorize_session)],
        body: Annotated[TicketErrorCreate, Form(
            media_type="multipart/form-data")],
    ):
        return await super().create(current_user, body)

    @classmethod
    async def update(
        cls,
        current_user: Annotated[Users | None, Depends(authorize_session)],
        id: str,
        body: Annotated[TicketErrorUpdate, Form(
            media_type="multipart/form-data")],
    ):
        return await super().update(current_user, id, body)


# Define the API routes
router.get(
    "/{id}",
    summary='Get Ticket Error Details',
    response_model=TicketError)(
    TicketErrorAPI.get)

router.post(
    "/",
    summary='Create New Ticket Error',
    response_model=TicketError)(
    TicketErrorAPI.create)

router.put(
    "/{id}",
    summary='Update Ticket Error',
    response_model=TicketError)(
    TicketErrorAPI.update)

router.delete(
    "/{id}",
    summary='Delete Ticket Error')(
    TicketErrorAPI.delete)
