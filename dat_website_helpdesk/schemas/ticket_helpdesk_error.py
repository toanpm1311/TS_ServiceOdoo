from datetime import datetime
from enum import Enum
from typing import List, Optional

from fastapi import File, UploadFile
from odoo.addons.core_fastapi.schemas import Attachment, BaseModel, BaseORM
from pydantic import Field


class TicketErrorSeverityCode(str, Enum):
    high = 'high'
    medium = 'medium'
    low = 'low'


class TicketErrorStateCode(str, Enum):
    new = 'new'
    in_progress = 'in_progress'
    done = 'done'
    cannot_fix = 'cannot_fix'
    waiting_spare = 'waiting_spare'


class TicketErrorAcceptanceStatusCode(str, Enum):
    before_acceptance = 'before_acceptance'
    after_acceptance = 'after_acceptance'


class TicketHelpdesk(BaseORM):
    uuid: Optional[str | bool] = Field(default=None)
    name: Optional[str | bool] = Field(default=None)
    subject: Optional[str | bool] = Field(default=None)


class User(BaseORM):
    uuid: str
    name: Optional[str | bool] = Field(default=None)


class TicketErrorActivity(BaseORM):
    uuid: str
    name: Optional[str | bool] = Field(default=None)
    is_for_automation_dep: Optional[bool] = Field(default=None)
    is_for_energy_dep: Optional[bool] = Field(default=None)


class TicketError(BaseORM):
    uuid: str
    ticket_id: TicketHelpdesk
    activity: Optional[TicketErrorActivity | bool] = Field(default=None)
    date_detected: datetime
    detected_by: User
    description: str
    severity: str
    attachment_ids: Optional[list[Attachment] | bool] = Field(default=None)
    state: str
    acceptance_status: str
    resolution: Optional[str | bool] = Field(default=None)
    date_resolved: Optional[datetime | bool] = Field(default=None)


class TicketErrorCreate(BaseModel):
    ticket_id: str = Field(description='Ticket UUID')
    activity: Optional[str] = Field(
        default=None, description='Activity UUID')
    date_detected: Optional[datetime] = Field(default=None)
    detected_by: Optional[str] = Field(
        default=None, description='Detect User UUID')
    description: str
    severity: Optional[TicketErrorSeverityCode] = Field(default=None)
    attachment_ids: Optional[List[UploadFile]] = File(default=None)
    state: Optional[TicketErrorStateCode] = Field(default=None)
    acceptance_status: Optional[TicketErrorAcceptanceStatusCode] = Field(default=None)
    resolution: Optional[str | bool] = Field(default=None)
    date_resolved: Optional[datetime | bool] = Field(default=None)


class TicketErrorUpdate(BaseModel):
    activity: Optional[str] = Field(
        default=None, description='Activity UUID')
    date_detected: Optional[datetime] = Field(default=None)
    detected_by: Optional[str] = Field(
        default=None, description='Detect User UUID')
    description: Optional[str] = Field(default=None)
    severity: Optional[TicketErrorSeverityCode] = Field(default=None)
    attachment_ids: Optional[List[UploadFile]] = File(default=None)
    state: Optional[str] = Field(default=None)
    resolution: Optional[str | bool] = Field(default=None)
    date_resolved: Optional[datetime | bool] = Field(default=None)
