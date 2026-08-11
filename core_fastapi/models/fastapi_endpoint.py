import re
from typing import Any

from fastapi import APIRouter
from odoo import _, api, exceptions, fields, models

from ..routers import router


class FastapiEndpoint(models.Model):
    _inherit = "fastapi.endpoint"

    app: str = fields.Selection(
        selection_add=[("core_fastapi", "Core FastAPI")], ondelete={"core_fastapi": "cascade"}
    )

    def _prepare_fastapi_routers(self, old_routers, new_router):
        new_routers = []
        for old_router in old_routers:
            # remove routes which will be overwriten in the current module
            route_names = [(r.path, tuple(r.methods))
                           for r in new_router.routes]
            new_routes = [
                r for r in old_router.routes if (r.path, tuple(r.methods)) not in route_names]
            if not new_routes:
                continue
            old_router.routes = new_routes
            new_routers.append(old_router)
        if self.app == "core_fastapi":
            # add router to the begin of routers to overwrite apis
            new_routers.insert(0, new_router)
        return new_routers

    def _get_fastapi_routers(self) -> list[APIRouter]:
        # Add router defined for tests to the demo app
        self.ensure_one()
        old_routers = super()._get_fastapi_routers()
        return self._prepare_fastapi_routers(old_routers, router)

    @api.constrains("root_path")
    def _check_root_path(self):
        super()._check_root_path()
        for rec in self:
            if not re.fullmatch(r'/api/v\d+', rec.root_path):
                raise exceptions.UserError(
                    _("Root Path must be /api/v[integer] . Ex: /api/v1"))

    def _prepare_fastapi_app_params(self) -> dict[str, Any]:
        res = super()._prepare_fastapi_app_params()
        config_parameter = self.env['ir.config_parameter'].sudo()
        api_debug = bool(config_parameter.get_param(
            'core_fastapi.api_debug'))
        if not api_debug:
            # Hide the api docs in the production environment
            res["openapi_url"] = None
        return res
