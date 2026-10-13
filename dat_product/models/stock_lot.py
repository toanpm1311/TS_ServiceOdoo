from odoo import models, fields, api


class StockLot(models.Model):
    _inherit = 'stock.lot'

    _sql_constraints = [
        ('unique_serial_number', 'unique(name)', 'The Serial Number must be unique!')
    ]

    health_log_ids = fields.One2many('serial.health.history', 'lot_id', string='Product Health', readonly=True)
    vendor_warranty_expiry = fields.Datetime(
        string='Vendor Warranty Expiry',
        copy=False,
        readonly=True,
    )
    installation_date = fields.Datetime(
        string="Installation Date",
        readonly=True,
        help="Automatically set when installation description is updated",
        copy=False,
    )
    installation_description = fields.Text(
        string="Installation Description",
        help="Describe what was done during installation"
    )
    installation_handler = fields.Many2one(
        'res.users',
        string="Installation Handler",
        readonly=True,
        help="User who last updated the installation description",
        copy=False,
    )

    @api.onchange('installation_description')
    def _onchange_installation_description(self):
        if self.installation_description:
            now = fields.Datetime.now()
            self.installation_date = now
            self.installation_handler = self.env.user

    def write(self, vals):
        vals = dict(vals)
        if 'product_id' in vals and 'warranty_month' not in vals:
            product = self.env['product.product'].browse(vals.get('product_id')).exists()
            vals['warranty_month'] = product.sap_wmonth if product else 0
        if 'installation_description' in vals:
            vals['installation_date'] = fields.Datetime.now()
            vals['installation_handler'] = self.env.uid
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            if 'warranty_month' not in vals and vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id']).exists()
                vals['warranty_month'] = product.sap_wmonth if product else 0
            if vals.get('installation_description'):
                vals['installation_date'] = fields.Datetime.now()
                vals['installation_handler'] = self.env.uid
            prepared_vals_list.append(vals)
        return super().create(prepared_vals_list)
