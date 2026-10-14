from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from odoo.addons.fastapi.context import odoo_env_ctx
from odoo.addons.fastapi.dependencies import fastapi_endpoint_id
from odoo.http import request


def authorize_session():
    if not request.session.uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return request.env.user


async def authorize_session_or_api_key(
    endpoint_id: Annotated[int, Depends(fastapi_endpoint_id)],
    api_key: Annotated[str | None, Header(
        alias='X-API-Key',
        description='System Parameter key whose value is the permitted API path.',
    )] = None,
):
    if api_key is None:
        return authorize_session()

    # An explicit key takes precedence over cookies, including invalid keys.
    api_key = api_key.strip()
    # Previous fixed configuration names are not themselves secret API keys.
    if not api_key or api_key in (
        'core_fastapi.api_key',
        'core_fastapi.api_key_endpoint',
        'core_fastapi.api_key_user_login',
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid API key',
        )

    # Native System Parameters: Key = API secret, Value = allowed route.
    parameters = request.env['ir.config_parameter'].sudo()
    configured_path = (parameters.get_param(api_key) or '').strip()
    if not configured_path:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid API key',
        )
    if request.httprequest.path.rstrip('/') != (
        '/' + configured_path.strip('/')
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid API key endpoint',
        )

    # Reuse the execution user already configured on the mounted FastAPI app.
    endpoint = request.env['fastapi.endpoint'].sudo().browse(endpoint_id).exists()
    user = endpoint.user_id if endpoint else None
    # Odoo's built-in Public User is deliberately inactive for interactive login.
    if not endpoint or not endpoint.active or not user or (
        not user.active and not user._is_public()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid API key',
        )

    # Do not inherit another session's company context or superuser mode.
    context = dict(request.env.context)
    context.pop('force_company', None)
    context.update(
        lang=user.lang or context.get('lang'),
        tz=user.tz,
        allowed_company_ids=(
            [endpoint.company_id.id] if endpoint.company_id else user.company_ids.ids
        ),
    )
    request.update_env(user=user.id, context=context, su=False)
    # This dependency is async so the context also reaches downstream FastAPI
    # dependencies and response serialization in the same request task.
    odoo_env_ctx.set(request.env)
    return request.env.user


def format_query(q: str = None):
    return q.strip() if q else q
