from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    code = fields.Char(size=20)
    partner_id = fields.Many2one('res.partner', 'Address', default=lambda self: self.company_id.partner_id,
                                 check_company=True)
