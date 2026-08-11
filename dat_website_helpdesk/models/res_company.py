from odoo import fields, models


class Company(models.Model):
    _name = 'res.company'
    _inherit = ['res.company', 'abstract.uuid']

    name = fields.Char(translate=True)
    prefix = fields.Char(string='Prefix')
    default_sale_whs_id = fields.Many2one(
        'stock.warehouse', string='Default Sale Warehouse')
    default_service_whs_id = fields.Many2one(
        'stock.warehouse', string='Default Service Warehouse')
