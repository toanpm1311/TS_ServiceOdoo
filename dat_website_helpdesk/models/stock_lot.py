from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.addons.dat_website_helpdesk.tools.validate_phone import is_valid_phone_number
from odoo.exceptions import ValidationError


class StockLot(models.Model):
    _name = 'stock.lot'
    _inherit = 'stock.lot'

    buyer_id = fields.Many2one('res.partner', tracking=True)
    buyer_phone = fields.Char(string='Buyer Phone', related='buyer_id.phone', readonly=False)
    owner_id = fields.Many2one('res.partner', tracking=True)
    owner_phone = fields.Char(string='Owner Phone', related='owner_id.phone', readonly=False)
    helpdesk_ticket_ids = fields.One2many('ticket.helpdesk', 'stock_lot_id', string='Tickets')
    warranty_start_date = fields.Datetime(string='Warranty Start Date')
    warranty_end_date = fields.Datetime(string='Warranty End Date', compute='_compute_warranty_end_date', store=True)
    warranty_status = fields.Selection([('warranty','Warranty'), ('out_of_warranty', 'Out of Warranty')],
                                       string='Warranty Status', compute='_compute_warranty_status')
    replaced_by = fields.Many2one('stock.lot', string='Replaced By')
    warranty_month = fields.Integer(string='Warranty Month')
    saleperson_id = fields.Many2one('hr.employee', string='Salesperson')
    branch = fields.Many2one('res.company', string='Branch', related='saleperson_id.company_id')
    department_id = fields.Many2one('hr.department', string='Department', related='saleperson_id.department_id')
    number_of_warranty = fields.Integer(string='Number of Warranty', compute='_compute_number_of_warranty')
    product_name = fields.Char(string='Item Name', related='product_id.name')

    @api.model
    def _helpdesk_find_product_by_code(self, product_code):
        product_code = (product_code or '').strip()
        if not product_code:
            return self.env['product.product']

        Product = self.env['product.product'].with_context(active_test=False)
        domains = [
            [('default_code', '=', product_code)],
            [('product_tmpl_id.default_code', '=', product_code)],
            [('product_tmpl_id.sap_model', '=', product_code)],
            [('product_tmpl_id.sap_code_po', '=', product_code)],
            [('product_tmpl_id.sap_serial_num', '=', product_code)],
            [('sap_model', '=', product_code)],
            [('sap_code_po', '=', product_code)],
            [('sap_serial_num', '=', product_code)],
            [('default_code', '=ilike', '%s%%' % product_code)],
            [('product_tmpl_id.default_code', '=ilike', '%s%%' % product_code)],
            [('product_tmpl_id.sap_model', '=ilike', '%s%%' % product_code)],
            [('product_tmpl_id.sap_code_po', '=ilike', '%s%%' % product_code)],
            [('product_tmpl_id.sap_serial_num', '=ilike', '%s%%' % product_code)],
            [('sap_model', '=ilike', '%s%%' % product_code)],
            [('sap_code_po', '=ilike', '%s%%' % product_code)],
            [('sap_serial_num', '=ilike', '%s%%' % product_code)],
            [('default_code', 'ilike', product_code)],
            [('product_tmpl_id.default_code', 'ilike', product_code)],
            [('product_tmpl_id.sap_model', 'ilike', product_code)],
            [('product_tmpl_id.sap_code_po', 'ilike', product_code)],
            [('product_tmpl_id.sap_serial_num', 'ilike', product_code)],
            [('sap_model', 'ilike', product_code)],
            [('sap_code_po', 'ilike', product_code)],
            [('sap_serial_num', 'ilike', product_code)],
        ]
        for domain in domains:
            product = Product.search(domain, limit=1)
            if product:
                return product
        return Product

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        product_code = self.env.context.get('helpdesk_product_code')
        if 'product_id' in fields_list and not values.get('product_id'):
            product = self._helpdesk_find_product_by_code(product_code)
            if product:
                values['product_id'] = product.id
                product_code = product.product_tmpl_id.default_code or product.default_code or product_code
        if 'ref' in fields_list and not values.get('ref') and product_code:
            values['ref'] = product_code
        return values

    def _helpdesk_product_ref(self):
        self.ensure_one()
        product = self.product_id
        return (
            product.product_tmpl_id.default_code
            or product.default_code
            or product.product_tmpl_id.sap_model
            or product.product_tmpl_id.sap_code_po
            or product.sap_model
            or product.sap_code_po
            or False
        ) if product else False

    @api.onchange('product_id')
    def _onchange_product_id_helpdesk_defaults(self):
        for lot in self:
            if not lot.product_id:
                continue
            product_ref = lot._helpdesk_product_ref()
            if product_ref:
                lot.ref = product_ref
            if not lot.warranty_month:
                lot.warranty_month = lot.product_id.sap_wmonth or 0

    @api.constrains('buyer_phone')
    def _check_buyer_phone(self):
        for rec in self:
            if rec.buyer_phone and not is_valid_phone_number(rec.buyer_phone):
                raise ValidationError(_("The buyer phone number of %s is not valid. Please check again.") % rec.name)

    @api.constrains('owner_phone')
    def _check_owner_phone(self):
        for rec in self:
            if rec.owner_phone and not is_valid_phone_number(rec.owner_phone):
                raise ValidationError(_("The owner phone number of %s is not valid. Please check again.") % rec.name)

    @api.depends('helpdesk_ticket_ids', 'helpdesk_ticket_ids.request_type')
    def _compute_number_of_warranty(self):
        for lot in self:
            lot.number_of_warranty = len(lot.helpdesk_ticket_ids.filtered(lambda x: x.request_type == 'warranty'))

    @api.depends('warranty_start_date', 'warranty_month')
    def _compute_warranty_end_date(self):
        for rec in self:
            if rec.warranty_start_date and rec.warranty_month:
                rec.warranty_end_date = rec.warranty_start_date + relativedelta(months=rec.warranty_month)
            else:
                rec.warranty_end_date = False

    @api.depends('warranty_end_date')
    def _compute_warranty_status(self):
        for rec in self:
            if rec.warranty_end_date:
                if fields.Datetime.now() <= rec.warranty_end_date:
                    rec.warranty_status = 'warranty'
                else:
                    rec.warranty_status = 'out_of_warranty'
            else:
                rec.warranty_status = False

    @api.onchange('buyer_id')
    def _onchange_buyer_id(self):
        if not self.owner_id and self.buyer_id:
            self.owner_id = self.buyer_id.id

    def reassign_owner_id(self):
        for rec in self:
            if rec.owner_id or not rec.buyer_id:
                continue
            rec.owner_id = rec.buyer_id.id

    def write(self, vals):
        res = super().write(vals)
        self.reassign_owner_id()
        return res
