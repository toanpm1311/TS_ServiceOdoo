from odoo import models, fields, api


class StockLot(models.Model):
    _inherit = 'stock.lot'

    _sql_constraints = [
        ('unique_serial_number', 'unique(name)', 'The Serial Number must be unique!')
    ]

    health_log_ids = fields.One2many('serial.health.history', 'lot_id', string='Product Health', readonly=True)
    warranty_month = fields.Integer(compute='_compute_warranty_month', store=True, readonly=False)
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

    @api.depends('product_id')
    def _compute_warranty_month(self):
        for rec in self:
            rec.warranty_month = rec.product_id.sap_wmonth if rec.product_id else 0

    def write(self, vals):
        if 'installation_description' in vals:
            vals['installation_date'] = fields.Datetime.now()
            vals['installation_handler'] = self.env.uid
        return super().write(vals)

    @api.model
    def create(self, vals):
        if vals.get('installation_description'):
            vals['installation_date'] = fields.Datetime.now()
            vals['installation_handler'] = self.env.uid
        return super().create(vals)
