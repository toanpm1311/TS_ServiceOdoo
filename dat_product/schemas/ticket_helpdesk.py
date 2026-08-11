from enum import Enum
from typing import Optional

from odoo.addons.dat_website_helpdesk.schemas import TicketHelpdeskBase
from pydantic import Field


class TicketBusinessUnit(str, Enum):
    AUT = 'AUT'
    ELE = 'ELE'


class TicketHelpdeskByBusinessUnit(TicketHelpdeskBase):
    business_unit: Optional[str | bool] = Field(default=None)
