from odoo import api, fields, models, _

class ProductBusinessUnit(models.Model):
    _name = 'product.business.unit'
    _description = 'Product Business Unit'
    _rec_name = 'code'
    _order = 'code'

    code = fields.Char(string='BU Code', required=True, copy=False, index=True)
    name = fields.Char(string='Description', required=True, copy=False)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'BU Code must be unique'),
    ]