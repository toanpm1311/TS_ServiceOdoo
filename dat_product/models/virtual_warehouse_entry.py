from odoo import api, fields, models, _

class VirtualWarehouseEntry(models.Model):
    """
    Virtual Warehouse to record serial lot entries and exits
    """
    _name = 'virtual.warehouse.entry'
    _description = 'Virtual Warehouse Serial Records'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    lot_id = fields.Many2one(
        'stock.lot',
        string='Serial Number',
        required=True,
        readonly=True,
        tracking=True
    )
    ticket_id = fields.Many2one(
        'ticket.helpdesk',
        string='Helpdesk Ticket',
        required=True,
        readonly=True,
        tracking=True
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        compute='_compute_product_id',
        store=True,
        readonly=True
    )
    status = fields.Selection([
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
    ],
        string='Status',
        default='in',
        tracking=True
    )
    entry_date = fields.Datetime(
        string='Entry Date',
        default=fields.Datetime.now,
        readonly=True
    )
    exit_date = fields.Datetime(
        string='Exit Date',
        readonly=True
    )
    note = fields.Text(
        string='Note'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        change_default=True
    )

    _sql_constraints = [
        (
            'lot_ticket_unique',
            'UNIQUE(lot_id, ticket_id)',
            _('This lot has already been recorded for this ticket!')
        ),
    ]

    @api.depends('lot_id')
    def _compute_product_id(self):
        for rec in self:
            rec.product_id = rec.lot_id.product_id if rec.lot_id else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('entry_date', fields.Datetime.now())
        return super().create(vals_list)

    def write(self, vals):
        if 'status' in vals and vals.get('status') == 'out':
            vals['exit_date'] = fields.Datetime.now()
        return super().write(vals)
