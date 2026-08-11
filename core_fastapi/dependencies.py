from fastapi import HTTPException, status
from odoo.http import request


def authorize_session():
    if not request.session.uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return request.env.user


def format_query(q: str = None):
    return q.strip() if q else q
