from typing import Annotated

from fastapi import Header, HTTPException, status
from odoo.addons.fastapi.context import odoo_env_ctx
from odoo.http import request


def authorize_session():
    if not request.session.uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return request.env.user


async def authorize_session_or_api_key(
    api_key: Annotated[str | None, Header(
        alias='X-API-Key',
        description='Odoo API key of the account used to read tickets.',
    )] = None,
):
    if api_key is None:
        return authorize_session()

    # An explicit key takes precedence over cookies, including invalid keys.
    api_key = api_key.strip()
    uid = request.env['res.users.apikeys']._check_credentials(
        scope='rpc', key=api_key,
    ) if api_key else None
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid API key',
        )

    # Read the owner's preferences before switching out of the public env.
    user = request.env['res.users'].sudo().browse(uid).exists()
    if not user or not user.active:
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
        allowed_company_ids=user.company_ids.ids,
    )
    request.update_env(user=uid, context=context, su=False)
    # This dependency is async so the context also reaches downstream FastAPI
    # dependencies and response serialization in the same request task.
    odoo_env_ctx.set(request.env)
    return request.env.user


def format_query(q: str = None):
    return q.strip() if q else q
