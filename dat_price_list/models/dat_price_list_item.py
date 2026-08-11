# -*- coding: utf-8 -*-

from odoo import api, fields, models


class DatPriceListItem(models.Model):
    _name = 'dat.price.list.item'
    _description = 'DAT Price List Item'
    _order = 'item_code'
    _rec_name = 'item_code'

    item_code = fields.Char(string='Item Code', required=True, index=True)
    description = fields.Char(string='Description')
    price = fields.Monetary(string='Price', required=True, default=0.0)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'item_code_company_unique',
            'unique(item_code, company_id)',
            'Item Code must be unique per company.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('item_code'):
                vals['item_code'] = vals['item_code'].strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('item_code'):
            vals['item_code'] = vals['item_code'].strip().upper()
        return super().write(vals)
