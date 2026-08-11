from odoo import fields, models, api


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'abstract.custom.view']

    sap_group_code = fields.Integer(string="SAP Group Code")
    sap_group_name = fields.Char(string="SAP Group Name")
    sap_slp_name = fields.Char(string="SAP Slp Name")
    sap_slp_code = fields.Integer(string="SAP Slp Code")
    sale_person = fields.Many2one(
        'hr.employee',
        string='SAP Sale Person',
        compute='_compute_sale_person',
        store=True,
        readonly=False,
        domain="[('sap_slp_code', '=', sap_slp_code)]"
    )
    sap_business_unit = fields.Char(string="SAP Business Unit")
    sap_cntct_code = fields.Integer(string="SAP Cntct Code")
    sap_cellolar = fields.Char(string="SAP Cellolar")
    sap_update_date = fields.Datetime(string="Update Date")
    sap_ship_to_code = fields.Char(string="SAP Ship To Code")
    sap_ship_to_address = fields.Char(string="SAP Ship To Address")
    sap_bill_to_code = fields.Char(string="SAP Bill To Code")
    sap_bill_to_address = fields.Char(string="SAP Bill To Address")
    is_sap_data= fields.Boolean(string="Is SAP Data", default=False)

    @api.depends('sap_slp_code')
    def _compute_sale_person(self):
        for partner in self:
            if partner.sap_slp_code and partner.sap_slp_code != -1:
                sale_person = self.env['hr.employee'].sudo().search(
                    [('sap_slp_code', '=', partner.sap_slp_code)],
                    limit=1
                )
                partner.sale_person = sale_person
            else:
                partner.sale_person = False
