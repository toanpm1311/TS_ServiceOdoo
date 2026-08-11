from odoo import _, models, fields, api
from odoo.exceptions import ValidationError


class TechnicalProposalTemplateLine(models.Model):
    _name = 'technical.proposal.template.line'
    _description = 'Technical Proposal Template Line'

    sequence = fields.Integer(string='Sequence', default=1)
    product_id = fields.Many2one('product.product', 'Product', index=True)
    default_code = fields.Char(related='product_id.default_code',string='Item Code', readonly=False)
    uom_id = fields.Many2one(related='product_id.uom_id', readonly=False)
    sap_brand = fields.Char(related='product_id.sap_brand', readonly=False)
    description = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0)
    technical_proposal_template_id = fields.Many2one('technical.proposal.template', string='Technical Proposal Template', required=True)
    note = fields.Char(string='Note')

    @api.constrains('quantity')
    def _check_quantity(self):
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(_("Quantity must be greater than 0."))
