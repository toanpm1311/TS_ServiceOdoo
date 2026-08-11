from typing import Annotated

from fastapi import APIRouter, Depends
from odoo import _
from odoo.addons.base.models.res_users import Users
from odoo.addons.web.controllers.session import Session
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request

from ..dependencies import authorize_session
from ..schemas import (
    OAuthProvider,
    User,
    UserChangePassword,
    UserLogin,
    UserLoginOAuth,
    UserResetPassword,
)
from ..utils import user as user_utils

router = APIRouter()


@router.post("/login", response_model=User)
def login(body: UserLogin):
    """
    Login with the login name and password
    """
    db = request.env.cr.dbname
    try:
        session = Session()
        res = session.authenticate(db, body.login, body.password)
        uid = res.get('uid')
        if uid:
            user = request.env['res.users'].browse(uid)
            return user
        raise UserError(_('User not found'))
    except AccessDenied:
        raise UserError(_('Wrong login/password'))


@router.post("/login-oauth", response_model=User)
def login_oauth(body: UserLoginOAuth):
    """
    Login with Azure use the JWT access token of the third-party application
    """
    provider_id = None
    if body.provider == OAuthProvider.azure:
        provider_id = request.env.ref('core_fastapi.provider_azure').id
    if not provider_id:
        raise UserError(_('Login with this provider is not enabled.'))
    return user_utils.login_oauth(access_token=body.access_token, state={'p': provider_id})


@router.post("/logout")
def logout():
    return request.session.logout(keep_db=True)


@router.post("/reset-password")
def reset_password(body: UserResetPassword):
    """
    This function similar the web_auth_reset_password function in the odoo base.
    Sends an email containing url to change password if not token or
    Receives the new password and save it if token is valid.
    """
    qcontext = user_utils.get_qcontext_password_reset(body.token)
    if not qcontext.get('token') and not qcontext.get('reset_password_enabled'):
        raise UserError(_('Could not reset your password'))
    if 'error' in qcontext:
        raise UserError(qcontext.get('error'))
    try:
        if qcontext.get('token'):
            if user_utils.save_new_password(qcontext, body.password, body.confirm_password):
                return {'detail': _('Password Successfully Updated')}
        else:
            if user_utils.send_password_reset_instruction(body.login):
                return {'detail': _('Password reset instructions sent to your email')}
    except Exception as e:
        raise UserError(str(e))


@router.post("/change-password")
def change_password(current_user: Annotated[Users | None, Depends(authorize_session)], body: UserChangePassword):
    try:
        request.env.user.change_password(
            old_passwd=body.old_password, new_passwd=body.new_password)
    except AccessDenied:
        raise UserError(_('Invalid Current Password'))
    return {'detail': _('Password Successfully Updated')}
