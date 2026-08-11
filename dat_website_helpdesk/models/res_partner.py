import re
from odoo.addons.dat_website_helpdesk.tools.validate_phone import is_valid_phone_number
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'abstract.uuid']

    owned_lot_ids = fields.One2many(
        'stock.lot', 'owner_id', string='Owned Serial Numbers')
    bought_lot_ids = fields.One2many(
        'stock.lot', 'buyer_id', string='Bought Serial Numbers')
    card_code = fields.Char(string='Card Code')

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = domain or []
        if name:
            name = name.split(' / ')[-1]
            domain = ['|', '|', '|', '|', ('name', operator, name), ('company_name', operator, name), ('email', operator, name),
                     ('phone', operator, name), ('card_code', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)
