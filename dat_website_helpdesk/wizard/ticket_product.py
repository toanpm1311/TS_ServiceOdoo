import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TicketProduct(models.TransientModel):
    _name = 'ticket.product'
    _description = 'Product Information for Ticket'

    ticket_wizard_id = fields.Many2one('create.ticket.wizard', string='Ticket Wizard', ondelete='cascade')
    owner_id = fields.Many2one('res.partner', string='Owner', store=True)
    buyer_id = fields.Many2one('res.partner', string='Buyer', store=True)
    serial_number = fields.Many2one('stock.lot', string='Serial Number', required=True)
    product_id = fields.Many2one('product.product', string='Product', store=True)
    product_code = fields.Char(string='Product Code', compute='_compute_product_code', store=True, readonly=False)
    error_description = fields.Text(string='Error Description')
    product_attachment_ids = fields.Many2many('ir.attachment', string="Upload File")
    note = fields.Text(string='Note')

    @api.depends('product_id', 'product_id.default_code', 'product_id.product_tmpl_id.default_code')
    def _compute_product_code(self):
        for record in self:
            product = record.product_id
            record.product_code = (
                product.product_tmpl_id.default_code
                or product.default_code
                or False
            ) if product else False

    @api.onchange('product_id')
    def _onchange_product_id(self):
        self._compute_product_code()

    @api.onchange('serial_number')
    def _onchange_serial_number(self):
        for record in self:
            if record.serial_number:
                record.product_id = record.serial_number.product_id.id or False
                record.product_code = (
                    record.serial_number.product_id.product_tmpl_id.default_code
                    or record.serial_number.product_id.default_code
                    or False
                )
                record.owner_id = record.serial_number.owner_id.id or False
                record.buyer_id = record.serial_number.buyer_id.id or False
            else:
                record.product_id = False
                record.product_code = False
                record.owner_id = False
                record.buyer_id = False
