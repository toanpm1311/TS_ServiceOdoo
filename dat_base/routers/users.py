from typing import Annotated

from fastapi import APIRouter, Depends
from odoo.addons.base.models.res_users import Users
from odoo.addons.core_fastapi.dependencies import authorize_session
from odoo.addons.core_fastapi.routers.users import UserAPI as UserAPICore

from ..schemas import User, UserUpdate

router = APIRouter()


class UserAPI(UserAPICore):
    @classmethod
    async def update_current_user(cls, current_user: Annotated[Users | None, Depends(authorize_session)],
                                  user_update: UserUpdate | bool = None):
        return await super().update_current_user(current_user, user_update)


# Define the API routes
router.get("/me", response_model=User)(
    UserAPI.get_current_user)

router.put("/me", response_model=User)(
    UserAPI.update_current_user)
