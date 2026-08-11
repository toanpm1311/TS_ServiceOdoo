from odoo import _, models, fields, api
from odoo.exceptions import ValidationError


class TechnicalProposalLine(models.Model):
    _name = 'technical.proposal.line'
    _description = 'Technical Proposal Line'

    sequence = fields.Integer(string='Sequence', default=1)
    product_id = fields.Many2one('product.product', 'Product', index=True)
    default_code = fields.Char(related='product_id.default_code',string='Item Code', readonly=False)
    uom_id = fields.Many2one(related='product_id.uom_id', readonly=False)
    sap_brand = fields.Char(related='product_id.sap_brand', readonly=False)
    description = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0)
    technical_proposal_id = fields.Many2one('technical.proposal', string='Technical Proposal', required=True)
    note = fields.Char(string='Note')
    onhand_quantity = fields.Float(string='On Hand Quantity', readonly=True)

    @api.constrains('quantity')
    def _check_quantity(self):
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(_("Quantity must be greater than 0."))
