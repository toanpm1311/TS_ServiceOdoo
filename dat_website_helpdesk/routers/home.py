from typing import Annotated

from fastapi import APIRouter, Depends
from odoo.addons.base.models.res_users import Users
from odoo.addons.core_fastapi.dependencies import authorize_session
from odoo.addons.core_fastapi.routers.base import BaseModelAPI
from odoo.http import request

from ..schemas import Home

router = APIRouter()


class HomeAPI(BaseModelAPI):
    @classmethod
    async def get_home_statistic(cls, current_user: Annotated[Users | None, Depends(authorize_session)]):
        ticket_model = request.env['ticket.helpdesk']
        domain = [('wf_external_id', 'in', ['workflow_2', 'workflow_4'])]
        return {
            'ticket_helpdesk': {
                'all': ticket_model.search_count(domain),
                'in_progress': ticket_model.search_count([*domain, ('status', '=', 'in_progress')]),
                'closed': ticket_model.search_count([*domain, ('status', '=', 'closed')]),
            }
        }


# Define the API routes
router.get(
    "/statistic",
    summary='Get Home Statistic',
    response_model=Home)(
    HomeAPI.get_home_statistic)
