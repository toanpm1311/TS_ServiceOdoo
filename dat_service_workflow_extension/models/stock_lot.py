from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    manufacturer_warranty_month = fields.Integer(
        string='B\u1ea3o h\u00e0nh h\u00e3ng (th\u00e1ng)',
        compute='_compute_manufacturer_warranty_month',
        readonly=True,
    )
    manufacturer_warranty_end_date = fields.Datetime(
        string='Ng\u00e0y h\u1ebft h\u1ea1n b\u1ea3o h\u00e0nh h\u00e3ng',
        related='vendor_warranty_expiry',
        readonly=True,
    )

    @api.depends('warranty_start_date', 'vendor_warranty_expiry')
    def _compute_manufacturer_warranty_month(self):
        for lot in self:
            if not lot.warranty_start_date or not lot.vendor_warranty_expiry:
                lot.manufacturer_warranty_month = 0
                continue

            difference = relativedelta(
                lot.vendor_warranty_expiry,
                lot.warranty_start_date,
            )
            lot.manufacturer_warranty_month = max(
                0,
                difference.years * 12 + difference.months,
            )
