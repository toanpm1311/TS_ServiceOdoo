from odoo import _, api, fields, models


class DatOpportunityActivity(models.Model):
    _name = 'dat.opportunity.activity'
    _description = 'DAT Opportunity Activity'

    opty_id = fields.Many2one(
        comodel_name='dat.opportunity',
        string='Opportunity',
        required=True,
        ondelete='cascade',
    )
    opty_code = fields.Char(string='Opportunity Code', required=True)
    contents = fields.Text()
    dat_create_date = fields.Date(
        string='DAT Create Date',
        default=fields.Date.context_today)
    attachment_ids = fields.Many2many('ir.attachment')
