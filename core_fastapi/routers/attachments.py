from typing import Annotated, List

from fastapi import APIRouter, Depends, Form
from odoo import Command, _
from odoo.addons.base.models.res_users import Users
from odoo.exceptions import ValidationError
from odoo.http import request

from ..dependencies import authorize_session
from ..schemas import Attachment, AttachmentsUpload
from .base import BaseModelAPI

router = APIRouter()


class AttachmentAPI(BaseModelAPI):
    _model_name = 'ir.attachment'

    @classmethod
    async def upload_attachments(
            cls,
            current_user: Annotated[Users | None, Depends(authorize_session)],
            body: Annotated[AttachmentsUpload, Form(media_type="multipart/form-data")] = None):
        record = False
        if body.res_id and body.res_model and body.res_field:
            record = request.env[body.res_model].validate_by_uuid(body.res_id)
        attachment_model = request.env['ir.attachment']
        attachment_vals = attachment_model.extract_attachment_vals_from_pydantic(
            body.files, record)
        if not attachment_vals:
            raise ValidationError(_('Attachment is invalid.'))
        attachments = attachment_model.create(attachment_vals)
        if attachments:
            if record:
                record.write({
                    body.res_field: [Command.link(aid)for aid in attachments.ids]})
            return attachments


# Define the API routes
router.post(
    "/",
    summary='Upload Attachments',
    response_model=List[Attachment])(AttachmentAPI.upload_attachments)

router.get(
    "/{id}",
    summary='Get Attachment',
    response_model=Attachment)(AttachmentAPI.get)

router.delete(
    "/{id}",
    summary='Delete Attachment')(AttachmentAPI.delete)
