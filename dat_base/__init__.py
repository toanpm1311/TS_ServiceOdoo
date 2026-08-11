from . import controllers
from . import models


def _dat_base_post_init(env):
    group_user = env.ref('base.group_user')
    group_uom = env.ref('uom.group_uom')
    if group_user and group_uom and group_uom.id not in group_user.implied_ids.ids:
        group_user._apply_group(group_uom)
    root_companies = env['res.company'].sudo().search(
        [('parent_id', '=', False)])
    vnd = env.ref('base.VND')
    for company in root_companies:
        company.currency_id = company.country_id.currency_id.id if company.country_id else vnd.id
