from fastapi import APIRouter
from odoo import models

from ..routers import router


class FastapiEndpoint(models.Model):
    _inherit = 'fastapi.endpoint'

    def _get_fastapi_routers(self) -> list[APIRouter]:
        self.ensure_one()
        old_routers = super()._get_fastapi_routers()
        return self._prepare_fastapi_routers(old_routers, router)
