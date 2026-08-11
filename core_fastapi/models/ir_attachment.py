import base64
from typing import List

from odoo import api, models

from ..schemas.common import BaseModel


class IrAttachment(models.Model):
    _name = 'ir.attachment'
    _inherit = ['ir.attachment', 'abstract.uuid']

    @api.model
    def extract_attachment_vals_from_pydantic(self, attach_files: List[BaseModel], instance: models.Model = None):
        """
        Return the values list to create new instance from the pydantic object
        """
        vals_list = [
            {
                'name': file.filename,
                'datas': base64.b64encode(file.file.read()),
                'public': True,
                'type': 'binary',
                'res_model': instance.model if instance else False,
                'res_id': instance.id if instance else False
            }
            for file in attach_files
        ]
        return vals_list
