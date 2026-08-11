from datetime import date
from typing import List, Optional

from fastapi import UploadFile
from odoo.addons.core_fastapi.schemas import Attachment, BaseModel, BaseORM
from pydantic import Field, field_validator


class OpportunityActivity(BaseORM):
    opty_id: Optional[str] = Field(default=None)
    opty_code: Optional[str] = Field(default=None)
    contents: Optional[str | bool] = Field(default=None)
    dat_create_date: Optional[date | bool] = Field(default=None)
    attachment_ids: Optional[List[Attachment] | bool] = Field(default=None)

    @field_validator('opty_id', mode='before')
    @classmethod
    def extract_opty_id(cls, value):
        return value.opty_id


class OpportunityActivityCreate(BaseModel):
    opty_code: Optional[str] = Field(default=None)
    contents: Optional[str | bool] = Field(default=None)
    dat_create_date: Optional[date | bool] = Field(default=None)
    attachment_ids: Optional[List[UploadFile] | bool] = Field(
        alias='attachments', default=None)


class Opportunity(BaseORM):
    opty_id: Optional[str] = Field(default=None)
    opty_code: Optional[str] = Field(default=None)
    installer_code: Optional[str | bool] = Field(default=None)
    card_code: Optional[str | bool] = Field(default=None)
    card_name: Optional[str | bool] = Field(default=None)
    territory: Optional[str | bool] = Field(default=None)
    business_unit: Optional[str | bool] = Field(default=None)
    contact_code: Optional[str | bool] = Field(default=None)
    contact_name: Optional[str | bool] = Field(default=None)
    cellular: Optional[str | bool] = Field(default=None)
    email: Optional[str | bool] = Field(default=None)
    identify_deci_maker: Optional[str | bool] = Field(default=None)
    topic: Optional[str | bool] = Field(default=None)
    capture_summary: Optional[str | bool] = Field(default=None)
    dat_create_date: Optional[date] = Field(default=None)


class OpportunityUpdate(BaseModel):
    installer_code: Optional[str | bool] = Field(default=None)
    card_code: Optional[str] = Field(default=None)
    card_name: Optional[str] = Field(default=None)
    territory: Optional[str] = Field(default=None)
    business_unit: Optional[str] = Field(default=None)
    contact_code: Optional[str] = Field(default=None)
    contact_name: Optional[str] = Field(default=None)
    cellular: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    identify_deci_maker: Optional[str] = Field(default=None)
    topic: Optional[str] = Field(default=None)
    capture_summary: Optional[str] = Field(default=None)
    dat_create_date: Optional[date] = Field(default=None)
