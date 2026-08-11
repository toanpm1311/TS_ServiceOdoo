from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    proposal_attachment_ids = fields.Many2many(
        'ir.attachment',
        'sale_order_proposal_attachment_rel',
        'order_id',
        'attachment_id',
        string='Proposal Attachments',
        domain=lambda self: [('res_model', '=', 'technical.proposal')],
        copy=False,
    )

    sc_sale_order_attachment_ids = fields.Many2many(
        'ir.attachment',
        'sale_order_attachment_rel',
        'order_id',
        'attachment_id',
        string='SC Order Attachments',
        domain=lambda self: [('res_model', '=', 'sale.order')],
        copy=False,
    )

    final_sale_order_attachment_ids = fields.Many2many(
        'ir.attachment',
        'final_sale_order_attachment_rel',
        'order_id',
        'attachment_id',
        string='Final Order Attachments',
        domain=lambda self: [('res_model', '=', 'sale.order')],
        copy=False,
    )
