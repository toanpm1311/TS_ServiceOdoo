from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from odoo import SUPERUSER_ID
from odoo.addons.fastapi.context import odoo_env_ctx
from odoo.addons.fastapi.dependencies import fastapi_endpoint_id
from odoo.http import request


API_KEY_PARAMETER = 'core_fastapi.api_key'


def authorize_session():
    if not request.session.uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return request.env.user


async def authorize_session_or_api_key(
    endpoint_id: Annotated[int, Depends(fastapi_endpoint_id)],
    api_key: Annotated[str | None, Header(
        alias='X-API-Key',
        description=f'Value of the {API_KEY_PARAMETER} system parameter.',
    )] = None,
):
    if api_key is None:
        return authorize_session()

    # An explicit key takes precedence over cookies, including invalid keys.
    api_key = api_key.strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid API key',
        )
    if request.httprequest.method != 'GET':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='API key is only supported for GET requests',
        )

    # Native System Parameters: fixed Key name, user-defined secret in Value.
    parameters = request.env['ir.config_parameter'].sudo()
    configured_key = (parameters.get_param(API_KEY_PARAMETER) or '').strip()
    if not configured_key or not compare_digest(
        api_key.encode('utf-8'), configured_key.encode('utf-8'),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid API key',
        )
    endpoint = request.env['fastapi.endpoint'].sudo().browse(endpoint_id).exists()
    if not endpoint or not endpoint.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid API key',
        )
    # The route is registered by the app, independently of the secret value.
    if request.httprequest.path.rstrip('/') != endpoint.root_path.rstrip('/') + '/tickets':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid API key endpoint',
        )

    # Administrators grant database-wide read access by creating the parameter.
    # Only this authenticated GET request is elevated; the session is untouched.
    companies = request.env['res.company'].sudo().search([], order='id')
    context = dict(request.env.context)
    context.pop('force_company', None)
    context['allowed_company_ids'] = companies.ids
    request.update_env(user=SUPERUSER_ID, context=context, su=True)
    # This dependency is async so the context also reaches downstream FastAPI
    # dependencies and response serialization in the same request task.
    odoo_env_ctx.set(request.env)
    return request.env.user


def format_query(q: str = None):
    return q.strip() if q else q
