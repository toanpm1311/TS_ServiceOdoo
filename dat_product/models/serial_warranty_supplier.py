from odoo import _, fields, models, api


class SerialWarrantySupplier(models.Model):
    """
    Represent for Serial Warranty in the supplier
    """
    _name = 'serial.warranty.supplier'
    _description = 'Stock Lot Warranty Supplier'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    lot_id = fields.Many2one(
        'stock.lot', string='Serial Number', readonly=True, required=True)
    product_id = fields.Many2one(
        'product.product', string='Product', compute='_compute_product_id', store=True, readonly=True)
    vendor = fields.Many2one('res.partner', string='Vendor')
    ticket_id = fields.Many2one('ticket.helpdesk', readonly=True, required=True)
    request_date = fields.Datetime(
        string='Request Date')
    error_description = fields.Text(
        string='Error Description')
    status = fields.Selection([
        ('new', 'New'),
        ('sent', 'Sent'),
        ('vendor_received', 'Vendor Received'),
        ('in_progress', 'In Progress'),
        ('vendor_returned', 'Vendor Returned'),
        ('stock_received', 'Stock Received')],
        default='new',
        tracking=True)
    company_id = fields.Many2one('res.company', string='Company', change_default=True,
                                 default=lambda self: self.env.company)

    _sql_constraints = [
        ("serial_ticket_uniq", "unique(lot_id, ticket_id)",
         _("The Serial Warranty in Supplier for this ticket already exists!")),
    ]

    @api.depends('lot_id')
    def _compute_product_id(self):
        for record in self:
            record.product_id = record.lot_id.product_id if record.lot_id else False
