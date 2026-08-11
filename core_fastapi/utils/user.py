import json

from odoo import SUPERUSER_ID, _
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request
from odoo.tools.misc import clean_context

auth_signup_controller = AuthSignupHome()


def save_new_password(qcontext: dict, password: str, confirm_password: str) -> bool:
    """
    Receives password and confirm_password, validate, extract userinfo from the qcontext token
    and save password
    """
    qcontext.update({
        'password': password,
        'confirm_password': confirm_password
    })
    auth_signup_controller.do_signup(qcontext)
    return True


def send_password_reset_instruction(login: str) -> bool:
    """
    Sends the reset password url to the email.
    """
    if not login:
        raise UserError(_('No login provided.'))
    request.env['res.users'].sudo().reset_password(login)
    return True


def get_qcontext_password_reset(token: str) -> dict:
    """
    Gets qcontext (includes keys in SIGN_UP_REQUEST_PARAMS) to use in the reset_password function
    """
    if token:
        # Prepare params to use in the get_auth_signup_qcontext function
        request.params['token'] = token
    return auth_signup_controller.get_auth_signup_qcontext()


def login_oauth(access_token: str, state: dict):
    """
    Login with Oauth use the JWT access token of the third-party application.
    Used for login with Social: Azure, Google,...
    """
    provider = state.get('p')
    request.update_context(**clean_context(state.get('c', {})))
    try:
        # auth_oauth may create a new user, the commit makes it visible to authenticate()'s own transaction below
        # Record does not exist or has been deleted. (Record: auth.oauth.provider(4,), User: 1)
        dbname, login, key = request.env['res.users'].with_user(SUPERUSER_ID).auth_oauth(
            provider, {'access_token': access_token, 'state': json.dumps(state)})
        request.env.cr.commit()
        uid = request.session.authenticate(dbname, login, key)
        if uid:
            return request.env['res.users'].browse(uid)
        raise UserError(_('User not found'))
    except UserError as e:
        raise e
    except AttributeError:
        # auth_signup is not installed
        raise UserError(_("Sign up is not allowed on this database."))
    except AccessDenied:
        # oauth credentials not valid, user could be on a temporary session
        raise UserError(_("You do not have access to this database or your invitation has expired. "
                          "Please ask for an invitation and be sure to follow the link in your invitation email."))
    except Exception:
        # signup error
        raise UserError(_("Access Denied"))
