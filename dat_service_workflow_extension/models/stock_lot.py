from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    manufacturer_warranty_month = fields.Integer(
        string='B\u1ea3o h\u00e0nh h\u00e3ng (th\u00e1ng)',
        related='product_id.sap_wmonth_dist',
        readonly=True,
    )
    manufacturer_warranty_end_date = fields.Datetime(
        string='Ng\u00e0y h\u1ebft h\u1ea1n b\u1ea3o h\u00e0nh h\u00e3ng',
        compute='_compute_manufacturer_warranty_end_date',
    )

    @api.depends('warranty_start_date', 'product_id.sap_wmonth_dist')
    def _compute_manufacturer_warranty_end_date(self):
        for lot in self:
            months = lot.product_id.sap_wmonth_dist
            lot.manufacturer_warranty_end_date = lot.warranty_start_date + relativedelta(months=months) if lot.warranty_start_date and months else False
