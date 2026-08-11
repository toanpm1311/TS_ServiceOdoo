from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request

from ..schemas import (
    TicketEleAutFullDataListResponse,
    TicketEleAutFullDataResponse,
)


router = APIRouter()


class TicketBusinessArea(str, Enum):
    ELE = 'ELE'
    AUT = 'AUT'


def _serialize_ticket(ticket, **options):
    return ticket.get_ele_aut_full_api_data(**options)


def _as_utc_naive(value):
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


@router.get(
    '/ele-aut/full-data',
    summary='Get full data of ELE and AUT sales tickets',
    response_model=TicketEleAutFullDataListResponse,
)
async def get_ele_aut_ticket_full_data(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query()] = None,
    ticket_status: Annotated[
        list[str] | None,
        Query(alias='status'),
    ] = None,
    business_area: Annotated[
        list[TicketBusinessArea] | None,
        Query(
            alias='area',
            description='ELE or AUT; repeat to select both.',
        ),
    ] = None,
    include_archived: Annotated[bool, Query()] = False,
    updated_since: Annotated[datetime | None, Query()] = None,
    updated_until: Annotated[datetime | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    include_related: Annotated[bool, Query()] = False,
    include_chatter: Annotated[bool, Query()] = False,
    include_binary: Annotated[bool, Query()] = False,
    related_limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    try:
        # Public by explicit integration requirement. Do not add the usual
        # authorize_session dependency; keep elevated access scoped here.
        ticket_model = request.env['ticket.helpdesk'].sudo()
        search_result = ticket_model.ele_aut_api_search_tickets(
            query=q,
            statuses=ticket_status,
            business_areas=business_area,
            include_archived=include_archived,
            updated_since=_as_utc_naive(updated_since),
            updated_until=_as_utc_naive(updated_until),
            cursor=cursor,
            offset=offset,
            limit=limit,
        )
        options = {
            'include_related': include_related,
            'include_chatter': include_chatter,
            'include_binary': include_binary,
            'related_limit': related_limit,
        }
        items = [
            _serialize_ticket(ticket, **options)
            for ticket in search_result['tickets']
        ]
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except (AccessError, MissingError, UserError) as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Ticket data could not be generated.',
        ) from error

    return {
        'count': search_result['total_count'],
        'offset': offset,
        'limit': limit,
        'returned_count': len(items),
        'has_more': search_result['has_more'],
        'next_cursor': search_result['next_cursor'],
        'snapshot_at': ticket_model._ele_aut_api_json_safe(
            search_result['snapshot_at'],
        ),
        'server_time': ticket_model._ele_aut_api_json_safe(
            search_result['server_time'],
        ),
        'updated_since': (
            ticket_model._ele_aut_api_json_safe(
                search_result['updated_since'],
            )
            if search_result['updated_since']
            else None
        ),
        'updated_until': ticket_model._ele_aut_api_json_safe(
            search_result['snapshot_at'],
        ),
        'items': items,
    }


@router.get(
    '/ele-aut/{identifier}/full-data',
    summary='Get full data of one ELE or AUT sales ticket',
    response_model=TicketEleAutFullDataResponse,
)
async def get_ele_aut_ticket_detail(
    identifier: str,
    business_area: Annotated[
        list[TicketBusinessArea] | None,
        Query(alias='area'),
    ] = None,
    include_related: Annotated[bool, Query()] = True,
    include_chatter: Annotated[bool, Query()] = True,
    include_binary: Annotated[bool, Query()] = False,
    related_limit: Annotated[int, Query(ge=1, le=2000)] = 500,
):
    ticket = request.env['ticket.helpdesk'].sudo().ele_aut_api_find_ticket(
        identifier,
        business_area,
    )
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='ELE/AUT ticket not found.',
        )
    try:
        return _serialize_ticket(
            ticket,
            include_related=include_related,
            include_chatter=include_chatter,
            include_binary=include_binary,
            related_limit=related_limit,
        )
    except (AccessError, MissingError, UserError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='ELE/AUT ticket not found.',
        ) from error
