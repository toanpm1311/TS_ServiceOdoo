import base64
import json
import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env['sale.order'].search([('ticket_id', '!=', False)])
    changes = []
    for order in orders:
        current = order.ticket_id.product_error_note or order.ticket_id.product_error_description or False
        if (order.ts_fault_description or False) != current:
            changes.append({
                'order_id': order.id, 'ticket_id': order.ticket_id.id,
                'old_description': order.ts_fault_description,
                'new_description': current,
            })
    if not changes:
        return
    backup = env['ir.attachment'].create({
        'name': 'quotation-fault-sync-17.0.1.0.3.json',
        'type': 'binary',
        'datas': base64.b64encode(json.dumps(changes, ensure_ascii=False).encode('utf-8')),
        'mimetype': 'application/json',
        'res_model': 'res.users', 'res_id': SUPERUSER_ID,
    })
    # Refresh old copied text once. Subsequent ticket corrections trigger the
    # stored compute; sent PDF attachments and queued notifications are untouched.
    env['sale.order'].browse([row['order_id'] for row in changes])._compute_ts_fault_description()
    _logger.warning(
        '[TS_FAULT_SYNC] refreshed=%s backup_attachment_id=%s', len(changes), backup.id,
    )
