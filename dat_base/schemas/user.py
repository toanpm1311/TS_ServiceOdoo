from typing import Optional

from odoo.addons.core_fastapi.schemas import User as UserCore
from odoo.addons.core_fastapi.schemas import UserUpdate as UserUpdateCore
from pydantic import Field


class User(UserCore):
    job_title: Optional[str | bool] = Field(default=None)
    sap_hr_code: Optional[str | bool] = Field(default=None)
    sap_position_hr: Optional[str | bool] = Field(default=None)
    role: Optional[str | bool] = Field(default=None)


class UserUpdate(UserUpdateCore):
    job_title: Optional[str | bool] = Field(default=None)
    sap_position_hr: Optional[str | bool] = Field(default=None)
