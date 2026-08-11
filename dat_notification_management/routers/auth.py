from typing import Annotated

from fastapi import APIRouter, Depends
from odoo.addons.base.models.res_users import Users
from odoo.addons.core_fastapi.dependencies import authorize_session
from odoo.http import request

from ..schemas import UserLogout

router = APIRouter()


@router.post("/logout")
def logout_and_clear_fcmtoken(current_user: Annotated[Users | None, Depends(authorize_session)], payload: UserLogout):
    fcm_token = payload.fcm_token
    if fcm_token:
        current_user.mail_firebase_tokens.filtered_domain(
            [('token', '=', fcm_token)]).unlink()
    return request.session.logout(keep_db=True)
