from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    lt_side_qty = fields.Float(string='LT Side Qty', copy=False, default=0.0)
    lt_lt_qty = fields.Float(string='LT Qty', copy=False, default=0.0)
    lt_main_qty = fields.Float(string='Main Qty', copy=False, default=0.0)
    lt_warehouse_code = fields.Char(string='LT Warehouse', copy=False)

    ts_alloc_main_qty = fields.Float(string='Allocated Main Qty', copy=False, default=0.0)
    ts_alloc_lt_qty = fields.Float(string='Allocated LT Qty', copy=False, default=0.0)
    ts_supply_side = fields.Selection(
        [
            ('main', 'Main'),
            ('lt', 'LT'),
            ('split', 'Split'),
            ('fallback_main', 'Fallback Main'),
            ('fallback_lt', 'Fallback LT'),
        ],
        string='Supply Side',
        copy=False,
    )
