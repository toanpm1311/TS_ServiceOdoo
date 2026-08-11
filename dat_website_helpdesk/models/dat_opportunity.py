from odoo import _, fields, models


class DatOpportunity(models.Model):
    _name = 'dat.opportunity'
    _description = 'DAT Opportunity'
    _rec_name = 'opty_code'

    opty_id = fields.Char(string='Opportunity ID', required=True)
    opty_code = fields.Char(string='Opportunity Code', required=True)
    installer_code = fields.Char(string='Installer Card Code')
    card_code = fields.Char(string='Customer Code')
    card_name = fields.Char(string='Customer Name')
    territory = fields.Char()
    business_unit = fields.Char()
    contact_code = fields.Char()
    contact_name = fields.Char()
    cellular = fields.Char()
    email = fields.Char()
    identify_deci_maker = fields.Char(string='Identify Decision Maker')
    topic = fields.Char()
    capture_summary = fields.Char()
    dat_create_date = fields.Date(
        string='DAT Create Date',
        default=fields.Date.context_today)
    activity_ids = fields.One2many(
        'dat.opportunity.activity',
        'opty_id',
        string='Activities'
    )

    _sql_constraints = [
        ("opty_code_unique", "unique(opty_code)",
         _("The opty_code must be unique.")),
        ("opty_id_unique", "unique(opty_id)",
         _("The opty_id must be unique.")),
    ]
