from datetime import datetime
from typing import Optional

from odoo.addons.core_fastapi.schemas import BaseModel, BaseORM
from pydantic import Field


class UserFcmToken(BaseModel):
    os: Optional[str | bool] = Field(default=None, description="Device OS")
    token: Optional[str | bool] = Field(default=None, description="Fcm Token")


class NotificationType(BaseORM):
    code: Optional[str | bool] = None
    name: Optional[str | bool] = None


class UserNotification(BaseORM):
    uuid: str = Field(default=None, description="UUID")
    title: str = Field(default=None, description="Title")
    body: str = Field(default=None, description="Body")
    target_action: Optional[str | bool] = Field(
        default=None, description="Action when click on the notification")
    screen_type: Optional[str | bool] = Field(
        default=None, description="Type of screen to do the target action")
    unread: bool = Field(default=None, description="Is unread notification?")
    target_record_uuid: Optional[str | bool] = Field(
        default=None, description="Target record UUID")
    create_date: datetime = Field(default=None, description="Created On")
    notification_type_id: NotificationType | bool = Field(
        default=None, description="Notification Type")


class UserNotificationUpdate(BaseModel):
    unread: bool = Field(default=None, description="Is unread notification")


class UserLogout(BaseModel):
    fcm_token: str = Field(default=None)
