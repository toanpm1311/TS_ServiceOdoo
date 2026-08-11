from odoo.addons.core_fastapi.schemas import BaseModel


class HomeTicket(BaseModel):
    all: int
    in_progress: int
    closed: int


class Home(BaseModel):
    ticket_helpdesk: HomeTicket
