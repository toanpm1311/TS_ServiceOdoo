from enum import Enum

from odoo.addons.fastapi.schemas import Paging
from odoo.http import request

from ..schemas import OrderBy


def get_masterdata(
        model_name,
        key_field: str,
        value_field: str,
        limit: int,
        offset: int,
        domain: list = None,
        query: str = None,
        sort_by: str = None,
        order_by: str = 'asc',
        active_test: bool = False):
    domain = domain or []
    model = request.env[model_name]
    if query:
        domain.append((value_field, 'ilike', query))
    records = model.with_context(active_test=active_test).web_search_read(
        domain=domain,
        specification={key_field: {}, value_field: {}},
        order=(sort_by or value_field) + ' ' + order_by,
        limit=limit,
        offset=offset
    )['records']
    results = [{'key': i[key_field], 'value': i.get(
        value_field)} for i in records if i.get(key_field)]
    total = model.search_count(domain)
    return results, total


def get_list_api_response(model: str, domain: list, paging: Paging = None, sort_by: list = None, order_by: OrderBy = None, sudo: bool = False):
    order = None
    if sort_by and order_by:
        order = ','.join(
            map(lambda i: (i.value if isinstance(i, Enum) else i) + ' ' + order_by.value, sort_by))
    res_model = request.env[model]
    if sudo:
        res_model = res_model.sudo()
    records = res_model.search(
        domain=domain,
        order=order,
        limit=paging.limit if paging else None,
        offset=paging.offset if paging else 0
    )
    count = res_model.search_count(domain=domain)
    return records, count
