"""Load with runpy.run_path() in Odoo shell; see RESTORE_PRICES.md.

No database writes occur on import or while building a plan.
"""
import base64
import json
import math
import re
from datetime import datetime, timezone
from html.parser import HTMLParser


DOC_FIELDS = {'main': 'ts_main_so_doc_number', 'lt': 'ts_lt_so_doc_number'}
ROUTES = {'/CreateSOForWarrFix': 'main', '/CreateSOForWarrFix_LT': 'lt'}


class _Text(HTMLParser):
    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.feed(body or '')

    def handle_data(self, data):
        self.parts.append(data)

    def handle_endtag(self, tag):
        if tag in ('b', 'pre', 'p', 'div', 'br'):
            self.parts.append('\n')


def _number(value):
    if isinstance(value, bool):
        raise ValueError('Boolean is not a price')
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError('Invalid price')
    return result


def confirmed_payloads(messages, expected_docs):
    """Pair each request with the following success note for the saved SO.

    Request logs survive transaction rollback in the bridge. A request alone
    therefore cannot be used as proof of the price of a successful document.
    Messages must be in chronological (date, id) order for ONE source order.
    """
    pending = {}
    confirmed = {}
    for message in messages:
        text = ''.join(_Text(message['body']).parts)
        if 'SAP REQUEST PAYLOAD - ' in text:
            try:
                start = text.index('{')
                data, _ = json.JSONDecoder().raw_decode(text[start:])
                side = ROUTES.get(data.get('route'))
                if side:
                    pending[side] = (message['id'], data['payload'])
            except (ValueError, TypeError, KeyError, AttributeError):
                # Never fall back to an earlier request after a broken log.
                pending.clear()
        match = re.search(r'\b(Main|LT) SO created in SAP:\s*([^\s<]+)', text)
        if match:
            side = 'main' if match[1] == 'Main' else 'lt'
            request = pending.pop(side, None)
            if request and match[2] == expected_docs.get(side):
                confirmed[side] = request
    return list(confirmed.values())


def original_prices(payload, item_code):
    """Keep conflicting prices; callers must skip ambiguous batch items."""
    prices = set()
    for row in payload.get('Lines', []):
        if str(row.get('ItemCode') or '').strip() != item_code:
            continue
        # Price is net of discount. Only U_OrigiPrice represents price_unit.
        if 'U_OrigiPrice' not in row:
            raise ValueError('Missing U_OrigiPrice')
        prices.add(_number(row['U_OrigiPrice']))
    return prices


def _require_admin(env):
    if not env.is_admin():
        raise PermissionError('Run price recovery as an Odoo administrator')


def build_plan(env, order_ids=None):
    """Inspect all TechService lines at exactly 1, or only the chosen orders.

    Suggestions come from successfully logged SAP SO requests, including
    requests on the first order of a batch sharing the same SAP document.
    No fallback to today's product/DAT price is allowed.
    """
    _require_admin(env)
    domain = [('order_id.ticket_id', '!=', False), ('display_type', '=', False),
              ('price_unit', '=', 1.0)]
    if order_ids is not None:
        domain.append(('order_id', 'in', list(order_ids)))
    lines = env['sale.order.line'].search(domain, order='order_id, id')
    repairs, skipped = [], []
    evidence_cache = {}
    for line in lines:
        order = line.order_id
        row = {'order_id': order.id, 'order': order.name, 'line_id': line.id,
               'product': line.product_id.display_name, 'old_price': line.price_unit,
               'currency': order.currency_id.name, 'quantity': line.product_uom_qty,
               'discount': line.discount, 'product_id': line.product_id.id,
               'uom_id': line.product_uom.id}
        if order.state == 'cancel' or line.qty_invoiced:
            skipped.append(dict(row, reason='Cancelled order or invoiced line'))
            continue
        if order.id not in evidence_cache:
            sources = order
            for field in DOC_FIELDS.values():
                if field in order._fields and order[field]:
                    sources |= env['sale.order'].search([
                        (field, '=', order[field]),
                        ('company_id', '=', order.company_id.id),
                        ('currency_id', '=', order.currency_id.id),
                        ('ticket_id', '!=', False),
                    ])
            evidence = []
            for source in sources.sorted('id'):
                # A shared Main SO does not imply the same LT SO (or vice versa).
                docs = {side: str(source[field] or '').strip()
                        for side, field in DOC_FIELDS.items()
                        if field in source._fields and order[field]
                        and source[field] == order[field]}
                messages = env['mail.message'].search([
                    ('model', '=', 'sale.order'), ('res_id', '=', source.id),
                    ('body', 'ilike', 'SO'),
                ], order='date, id')
                evidence.extend((source.id, message_id, payload)
                                for message_id, payload in confirmed_payloads(
                                    [{'id': m.id, 'body': m.body} for m in messages], docs))
            evidence_cache[order.id] = evidence
        code = (order._get_line_item_code_for_sap(line)
                if hasattr(order, '_get_line_item_code_for_sap')
                else line.product_id.default_code) or ''
        code = code.strip()
        prices, references = set(), []
        invalid = False
        for source_id, message_id, payload in evidence_cache[order.id]:
            try:
                found = original_prices(payload, code)
            except (ValueError, TypeError, AttributeError):
                invalid = True
                continue
            if found:
                prices.update(found)
                references.append({'order_id': source_id, 'message_id': message_id})
        if not code or invalid or len(prices) != 1:
            skipped.append(dict(row, reason='Missing or conflicting historical prices',
                                candidate_prices=sorted(prices)))
        elif next(iter(prices)) == line.price_unit:
            skipped.append(dict(row, reason='Historical price is already 1'))
        else:
            repairs.append(dict(row, item_code=code, new_price=next(iter(prices)),
                                evidence=references))
    return {'version': 1, 'database': env.cr.dbname,
            'order_ids': sorted(lines.order_id.ids), 'repairs': repairs, 'skipped': skipped}


def save_plan(plan, filename):
    # Exclusive creation avoids overwriting the original review/backup file.
    with open(filename, 'x', encoding='utf-8') as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2)


def backup_plan(env, plan):
    """Keep recovery evidence and skipped lines, including empty recoveries."""
    _require_admin(env)
    return env['ir.attachment'].create({
        'name': 'so-price-recovery-%s.json' % datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'),
        'type': 'binary', 'mimetype': 'application/json',
        'datas': base64.b64encode(json.dumps(plan, ensure_ascii=False, indent=2).encode('utf-8')),
        'res_model': 'res.users', 'res_id': env.user.id,
    })


def apply_plan(env, plan):
    """Apply a recovery plan atomically; the caller owns the transaction.

    A database attachment preserves the before/after values and evidence.
    Revalidation aborts if a price, quantity, product, discount or evidence
    changed after preview. Re-running an already applied plan also aborts.
    """
    _require_admin(env)
    if plan.get('version') != 1 or plan.get('database') != env.cr.dbname:
        raise ValueError('Wrong plan version or target database')
    repairs = plan.get('repairs') or []
    if not repairs:
        return {'updated': 0, 'backup_attachment_id': False}
    order_ids = plan['order_ids']
    line_ids = [row['line_id'] for row in repairs]
    with env.cr.savepoint():
        env['sale.order'].flush_model()
        env['sale.order.line'].flush_model()
        env.cr.execute('SELECT id FROM sale_order WHERE id = ANY(%s) ORDER BY id FOR UPDATE NOWAIT',
                       (order_ids,))
        env.cr.execute('SELECT id FROM sale_order_line WHERE id = ANY(%s) ORDER BY id FOR UPDATE NOWAIT',
                       (line_ids,))
        env.invalidate_all()
        current = build_plan(env, order_ids=order_ids)
        if current['repairs'] != repairs:
            raise ValueError('Data or evidence changed. Generate and review a new plan.')
        backup = backup_plan(env, plan)
        for row in repairs:
            line = env['sale.order.line'].browse(row['line_id'])
            line.with_context(ts_allow_post_so_edit=True, ts_skip_price_impact=True).write({
                'price_unit': row['new_price'],
            })
        env.flush_all()
        env['sale.order.line'].browse(line_ids).invalidate_recordset(['price_unit'])
        for row in repairs:
            line = env['sale.order.line'].browse(row['line_id'])
            if line.price_unit != row['new_price']:
                raise ValueError('Price verification failed for line %s' % line.id)
    return {'updated': len(repairs), 'backup_attachment_id': backup.id}
