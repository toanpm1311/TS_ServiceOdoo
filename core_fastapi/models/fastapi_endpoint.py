import re
from copy import copy
from typing import Any

from fastapi import APIRouter
from odoo import _, api, exceptions, fields, models

from ..routers import router


def _route_keys(api_router, prefix=""):
    """Read both flattened routes and lazily included FastAPI routers."""
    for route in api_router.routes:
        child_router = getattr(route, "original_router", None)
        if child_router is not None:
            yield from _route_keys(
                child_router, prefix + route.include_context.prefix
            )
        elif hasattr(route, "path"):
            yield (prefix + route.path,
                   tuple(sorted(getattr(route, "methods", None) or ())))


def _without_overridden_routes(api_router, overridden, prefix=""):
    # Routers are module globals: keep their routes intact across app rebuilds.
    filtered_router = copy(api_router)
    filtered_routes = []
    for route in api_router.routes:
        child_router = getattr(route, "original_router", None)
        if child_router is not None:
            child_router = _without_overridden_routes(
                child_router, overridden, prefix + route.include_context.prefix
            )
            if child_router.routes:
                filtered_routes.append(type(route)(
                    original_router=child_router,
                    include_context=route.include_context,
                ))
        else:
            key = None
            if hasattr(route, "path"):
                key = (prefix + route.path,
                       tuple(sorted(getattr(route, "methods", None) or ())))
            if key not in overridden:
                filtered_routes.append(route)
    filtered_router.routes = filtered_routes
    return filtered_router


class FastapiEndpoint(models.Model):
    _inherit = "fastapi.endpoint"

    app: str = fields.Selection(
        selection_add=[("core_fastapi", "Core FastAPI")], ondelete={"core_fastapi": "cascade"}
    )

    def _prepare_fastapi_routers(self, old_routers, new_router):
        if self.app != "core_fastapi":
            return old_routers
        route_names = set(_route_keys(new_router))
        new_routers = []
        for old_router in old_routers:
            filtered_router = _without_overridden_routes(old_router, route_names)
            if filtered_router.routes:
                new_routers.append(filtered_router)
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
