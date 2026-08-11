from fastapi import APIRouter
from odoo.addons.core_fastapi.routers.auth import login as login_core
from odoo.addons.core_fastapi.routers.auth import login_oauth as login_oauth_core
from odoo.addons.core_fastapi.schemas import UserLogin, UserLoginOAuth

from ..schemas import User

router = APIRouter()


@router.post("/login", response_model=User)
def login(body: UserLogin):
    """
    Login with the login name and password
    """
    return login_core(body)


@router.post("/login-oauth", response_model=User)
def login_oauth(body: UserLoginOAuth):
    """
    Login with Azure use the JWT access token of the third-party application
    """
    return login_oauth_core(body)
