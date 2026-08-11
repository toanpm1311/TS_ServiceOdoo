from typing import Annotated

from fastapi import APIRouter, Depends
from odoo import _
from odoo.addons.base.models.res_users import Users
from odoo.addons.core_fastapi.dependencies import authorize_session
from odoo.addons.core_fastapi.routers.users import UserAPI as UserAPIBase
from odoo.addons.core_fastapi.schemas import OrderBy
from odoo.addons.core_fastapi.utils.common import get_list_api_response
from odoo.addons.fastapi.dependencies import paging
from odoo.addons.fastapi.schemas import PagedCollection, Paging
from odoo.http import request

from ..schemas import (
    NotificationType,
    UserFcmToken,
    UserNotification,
    UserNotificationUpdate,
)
from ..utils import notification as noti_utils

router = APIRouter()


class UserAPI(UserAPIBase):
    @classmethod
    async def save_my_fcm_token(
        cls,
        current_user: Annotated[Users | None, Depends(authorize_session)],
        fcm_token: UserFcmToken,
    ):
        """
        Saves the new fcm_token for the current user
        """
        exists_token = request.env['mail.firebase'].sudo().search(
            [('token', '!=', False), ('token', '=', fcm_token.token)])
        if exists_token:
            exists_token.sudo().unlink()
        mail_firebase = request.env['mail.firebase'].create({
            'user_id': current_user.id,
            'partner_id': current_user.partner_id.id,
            'os': fcm_token.os,
            'token': fcm_token.token,
        })
        return mail_firebase

    @classmethod
    async def get_my_notifications(
        cls,
        current_user: Annotated[Users | None, Depends(authorize_session)],
        paging: Annotated[Paging, Depends(paging)],
        unread: bool = None,
    ):
        """
        Get notifications of the current user
        """
        specification = dict(UserNotification())
        specification['notification_type_id'] = {
            'fields': dict(NotificationType())}
        domain = noti_utils.get_my_notifications_domain(current_user, filter_kwargs={
            'unread': unread,
        })
        records, count = get_list_api_response(
            model='res.users.notification',
            domain=domain,
            paging=paging,
            sort_by=['create_date'],
            order_by=OrderBy.desc,
        )
        return PagedCollection[UserNotification](
            count=count,
            items=records
        )

    @classmethod
    async def update_my_notifications(
        cls,
        current_user: Annotated[Users | None, Depends(authorize_session)],
        payload: UserNotificationUpdate,
        ids: list[str] = [],
    ):
        """
        Update all notifications of the current user
        """
        if ids:
            notifications = request.env['res.users.notification'].validate_by_uuids(
                ids)
        else:
            notifications = current_user.notifications
        notifications.write(payload.model_dump())
        return {'detail': _('All notifications was updated successfully.')}

    @classmethod
    async def count_unread_notifications(
        cls,
        current_user: Annotated[Users | None, Depends(authorize_session)],
    ):
        """
        Count the total of unread notifications of the current user
        """
        domain = noti_utils.get_my_notifications_domain(current_user, filter_kwargs={
            'unread': True,
        })
        count = request.env['res.users.notification'].search_count(
            domain=domain)
        return count


# Define the API routes
router.post("/me/fcm_token", response_model=UserFcmToken)(
    UserAPI.save_my_fcm_token)
router.get(
    "/me/notifications",
    summary='Get My Notifications',
    response_model=PagedCollection[UserNotification])(
    UserAPI.get_my_notifications)
router.get("/me/total_unread_notifications")(
    UserAPI.count_unread_notifications)
router.put("/me/notifications")(
    UserAPI.update_my_notifications)
