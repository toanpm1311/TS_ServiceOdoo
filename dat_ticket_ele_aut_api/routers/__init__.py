from fastapi import APIRouter

from .tickets import router as tickets_router


router = APIRouter()
router.include_router(tickets_router, prefix='/tickets', tags=['tickets'])

