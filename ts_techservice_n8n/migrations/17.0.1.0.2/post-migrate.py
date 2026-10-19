import logging

from odoo import SUPERUSER_ID, api
from odoo.addons.ts_techservice_n8n.tools.restore_so_prices import (
    apply_plan,
    backup_plan,
    build_plan,
)


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    plan = build_plan(env)
    result = apply_plan(env, plan)
    backup_id = result['backup_attachment_id']
    if not backup_id:
        backup_id = backup_plan(env, plan).id
    _logger.warning(
        '[TS_PRICE_RECOVERY] Upgrade from %s: restored=%s skipped=%s backup_attachment_id=%s',
        version, result['updated'], len(plan['skipped']), backup_id,
    )
    # Odoo owns the module upgrade transaction. Do not commit here: if any
    # upgrade step fails, both recovery and its backup must roll back together.
