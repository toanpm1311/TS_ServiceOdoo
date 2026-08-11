from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import ConfigDict, Field

from .common import BaseModel, BaseORM


class OAuthProvider(str, Enum):
    azure = 'azure'


class User(BaseORM):
    uuid: Optional[str | bool] = Field(default=None)
    login: Optional[str | bool] = Field(default=None)
    name: Optional[str | bool] = Field(default=None)
    email: Optional[str | bool] = Field(default=None)
    phone: Optional[str | bool] = Field(default=None)
    mobile: Optional[str | bool] = Field(default=None)
    avatar_256_url: Optional[str | bool] = Field(default=None)
    lang:  Optional[str | bool] = Field(default=None, title='Language Code')
    login_date: Optional[datetime | bool] = Field(
        default=None, title='Last Login')

    model_config = ConfigDict(from_attributes=True)


class UserChangePassword(BaseModel):
    old_password: str
    new_password: str


class UserLogin(BaseModel):
    login: str
    password: str


class UserLoginOAuth(BaseModel):
    access_token: str
    provider: OAuthProvider = OAuthProvider.azure


class UserResetPassword(BaseModel):
    token: Optional[str] = Field(default=None)
    login: str = Field(
        default=None, title="The login name of the user account.")
    password: Optional[str] = Field(default=None)
    confirm_password: Optional[str] = Field(default=None)


class UserUpdate(BaseModel):
    name: Optional[str | bool] = Field(default=None)
    email: Optional[str | bool] = Field(default=None)
    phone: Optional[str | bool] = Field(default=None)
    mobile: Optional[str | bool] = Field(default=None)
    active: bool = Field(default=None)
    lang: Optional[str | bool] = Field(default=None)


class UserCreate(UserUpdate):
    login: str
    password: str = Field(title="The password of the user account.")
