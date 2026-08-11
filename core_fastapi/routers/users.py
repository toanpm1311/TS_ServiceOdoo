import base64
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from odoo.addons.base.models.res_users import Users

from ..dependencies import authorize_session
from ..schemas import User, UserUpdate
from .base import BaseModelAPI

router = APIRouter()


class UserAPI(BaseModelAPI):
    _model_name = 'res.users'

    @classmethod
    async def get_current_user(cls, current_user: Annotated[Users | None, Depends(authorize_session)]):
        return current_user

    @classmethod
    async def update_current_user(cls, current_user: Annotated[Users | None, Depends(authorize_session)],
                                  user_update: UserUpdate | bool = None):
        current_user.write(user_update.model_dump(exclude_unset=True))
        return current_user

    @classmethod
    async def update_my_avatar(self, current_user: Annotated[Users | None, Depends(authorize_session)], avatar: UploadFile):
        current_user.image_1920 = base64.b64encode(avatar.file.read())
        return {'detail': current_user.avatar_256_url}


# Define the API routes
router.get("/me", response_model=User)(
    UserAPI.get_current_user)

router.put("/me", response_model=User)(
    UserAPI.update_current_user)

router.post("/me/avatar")(
    UserAPI.update_my_avatar)
