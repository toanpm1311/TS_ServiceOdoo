from datetime import datetime
from enum import Enum
from typing import Annotated

import pytz
from fastapi import APIRouter, Body, Depends, Query
from odoo import _
from odoo.addons.base.models.res_users import Users
from odoo.addons.fastapi.dependencies import paging
from odoo.addons.fastapi.schemas import PagedCollection, Paging
from odoo.http import request
from odoo.osv import expression

from ..dependencies import authorize_session, format_query
from ..schemas import BaseModel, BaseORM, OrderBy
from ..utils.common import get_list_api_response

router = APIRouter()


class BaseModelAPI:
    _model_name = ''
    _schema_list = BaseORM
    _schema_item = BaseORM

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def clean_attachment_fields(cls, vals, odoo_object=None):
        attachment_model = request.env['ir.attachment']
        for f_name in vals.keys():
            f_model = request.env[cls._model_name]._fields[f_name].comodel_name
            if f_model == 'ir.attachment':
                attachment_vals_list = attachment_model.extract_attachment_vals_from_pydantic(
                    vals[f_name])
                if odoo_object:
                    # clear old vals
                    getattr(odoo_object, f_name).unlink()
                vals[f_name] = [(0, 0, vals)
                                for vals in attachment_vals_list]
        return vals

    @classmethod
    def clean_update_and_creation_input(cls, body: BaseModel, odoo_object=None):
        updated_data = body.model_dump(exclude_unset=True)
        for key, value in updated_data.items():
            if isinstance(value, Enum):
                updated_data[key] = value.name
            if value and isinstance(value, datetime):
                dt_utc = value.astimezone(pytz.utc)
                dt_naive = dt_utc.replace(tzinfo=None)
                updated_data[key] = dt_naive

        updated_data = cls.clean_attachment_fields(updated_data, odoo_object)
        return updated_data

    @classmethod
    def get_list_search_domain(cls, q: str):
        return [('name', 'ilike', q)]

    @classmethod
    async def get(cls, current_user: Annotated[Users | None, Depends(authorize_session)], id: str):
        return request.env[cls._model_name].validate_by_uuid(id)

    @classmethod
    async def get_list(
        cls,
        current_user: Annotated[Users | None, Depends(authorize_session)],
        paging: Annotated[Paging, Depends(paging)],
        q: Annotated[str, Depends(format_query)] = None,
        order_by: OrderBy = None,
        sort_by: Annotated[list[str] | None, Query()] = None,
    ):
        domain = []
        if q:
            domain = expression.AND([domain, cls.get_list_search_domain(q)])
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
    async def create(cls, current_user: Annotated[Users | None, Depends(authorize_session)], body: Annotated[BaseModel, Body()] = None):
        cleaned_input = cls.clean_update_and_creation_input(body)
        new_record = request.env[cls._model_name].create(cleaned_input)
        return new_record

    @classmethod
    async def update(cls, current_user: Annotated[Users | None, Depends(authorize_session)], id: str, body: Annotated[BaseModel, Body()] = None):
        record = request.env[cls._model_name].validate_by_uuid(id)
        cleaned_input = cls.clean_update_and_creation_input(body, record)
        record.write(cleaned_input)
        return record

    @classmethod
    async def delete(cls, current_user: Annotated[Users | None, Depends(authorize_session)], id: str):
        request.env[cls._model_name].validate_by_uuid(id).unlink()
        return {'detail': _('Delete record successfully.')}

    @classmethod
    async def deactive(cls, current_user: Annotated[Users | None, Depends(authorize_session)], id: str):
        # soft delete
        request.env[cls._model_name].validate_by_uuid(
            id).write({'active': False})
        return {'detail': _('Deactive record successfully.')}
