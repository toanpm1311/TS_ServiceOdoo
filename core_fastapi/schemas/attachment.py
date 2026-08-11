from typing import List, Optional

from fastapi import UploadFile
from odoo.http import request
from pydantic import Field

from ..tools.text import is_url
from .common import BaseModel, BaseORM


class Attachment(BaseORM):
    uuid: Optional[str | bool] = Field(default=None)
    name: Optional[str | bool] = Field(default=None)
    local_url: Optional[str | bool] = Field(default=None, title='URL')

    def model_post_init(self, *args, **kwargs):
        super().model_post_init(*args, **kwargs)

        base_url = request.env['ir.config_parameter'].sudo(
        ).get_param('web.base.url') or ''
        for field, value in self:
            if field == 'local_url' and value and not is_url(value):
                value = base_url + value
                setattr(self, field, value)


class AttachmentData(Attachment):
    datas: Optional[str | bool] = Field(default=None, title='Base64 Data')


class AttachmentsUpload(BaseModel):
    files: List[UploadFile]
    res_id: str = Field(
        default=None, description='The UUID of the object to which the attachment will be uploaded')
    res_model: str = Field(
        default=None, description='The Odoo model to which this attachment is related')
    res_field: str = Field(
        default=None, description='The field name of the relation in the Odoo model')
