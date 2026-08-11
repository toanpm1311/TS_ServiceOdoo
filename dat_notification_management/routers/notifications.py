from typing import Annotated

from fastapi import APIRouter, Depends
from odoo import _
from odoo.addons.base.models.res_users import Users
from odoo.addons.core_fastapi.dependencies import authorize_session
from odoo.addons.core_fastapi.routers.base import BaseModelAPI
from odoo.http import request

from ..schemas import UserNotification, UserNotificationUpdate
from ..utils import notification as noti_utils

router = APIRouter()


class UserNotificationAPI(BaseModelAPI):
    _model_name = 'res.users.notification'

    @classmethod
    async def update_notification(
        cls,
        current_user: Annotated[Users | None, Depends(authorize_session)],
        id: str,
        payload: UserNotificationUpdate,
    ):
        """
        Update notification
        """
        noti = request.env[cls._model_name].validate_by_uuid(id)
        noti_utils.validate_notification(current_user, noti)
        noti.write(payload.dict())
        return noti

    @classmethod
    async def delete_notification(
        cls,
        current_user: Annotated[Users | None, Depends(authorize_session)],
        id: str,
    ):
        """
        Delete notification
        """
        noti = request.env[cls._model_name].validate_by_uuid(id)
        noti_utils.validate_notification(current_user, noti)
        noti.active = False
        return {'detail': _('Notification was deleted successfully.')}


# Define the API routes
router.put(
    "/{id}", response_model=UserNotification)(UserNotificationAPI.update_notification)
router.delete("/{id}")(UserNotificationAPI.delete_notification)
