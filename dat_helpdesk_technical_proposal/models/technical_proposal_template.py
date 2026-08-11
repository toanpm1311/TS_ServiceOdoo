from odoo import _, models, fields, api
from odoo.exceptions import ValidationError

class TechnicalProposalTemplate(models.Model):
    _name = 'technical.proposal.template'
    _description = 'Technical Proposal eBOM Template'
    _order = 'create_date'

    name = fields.Char(string='Technical Proposal Template Name', required=True)
    description = fields.Char(string='Technical Proposal Template Description')
    technical_proposal_template_line_ids = fields.One2many('technical.proposal.template.line', 'technical_proposal_template_id',
                                                  string='Proposal Template Lines', copy=True)
