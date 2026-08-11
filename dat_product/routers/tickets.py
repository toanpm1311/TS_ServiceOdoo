from typing import Annotated

from fastapi import APIRouter, Depends, Query
from odoo.addons.base.models.res_users import Users
from odoo.addons.core_fastapi.dependencies import authorize_session
from odoo.http import request
from odoo.osv import expression

from ..schemas import TicketBusinessUnit, TicketHelpdeskByBusinessUnit


router = APIRouter()


@router.get(
    '/by-business-units',
    summary='Get All Tickets By Business Unit',
    response_model=list[TicketHelpdeskByBusinessUnit],
)
async def get_tickets_by_business_unit(
    current_user: Annotated[Users | None, Depends(authorize_session)],
    business_units: Annotated[
        list[TicketBusinessUnit] | None,
        Query(description='Repeat this parameter to filter by AUT and/or ELE.'),
    ] = None,
):
    """Return all accessible tickets belonging to the requested business units."""
    units = business_units or list(TicketBusinessUnit)
    unit_codes = list(dict.fromkeys(unit.value for unit in units))
    domain = expression.OR([
        [('business_unit', '=ilike', code)]
        for code in unit_codes
    ])
    return request.env['ticket.helpdesk'].search(domain)
