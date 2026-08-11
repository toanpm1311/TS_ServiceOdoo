from fastapi import APIRouter

from .home import router as home_router
from .opportunities import router as opportunities_router
from .opportunity_activities import router as opportunity_activities_router
from .tickets import router as tickets_router
from .ticket_errors import router as ticket_errors_router

router = APIRouter()
router.include_router(home_router, prefix="/me/home", tags=["home"])
router.include_router(tickets_router, prefix="/tickets", tags=["tickets"])
router.include_router(opportunities_router,
                      prefix="/opportunities", tags=["opportunities"])
router.include_router(opportunity_activities_router,
                      prefix="/opportunity-activities", tags=["opportunity-activities"])
router.include_router(ticket_errors_router,
                      prefix="/ticket-errors", tags=["ticket-errors"])
