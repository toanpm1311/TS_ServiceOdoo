from odoo import api, fields, models
import logging


class HelpdeskType(models.Model):
    _name = 'helpdesk.type'
    _inherit = 'abstract.uuid'
    _description = 'Helpdesk Type'

    name = fields.Char(string='Type', translate=True)
    code = fields.Char('Code', compute='_compute_code', store=True)

    def _compute_code(self):
        res = self.get_external_id()
        for rec in self:
            rec.code = res.get(rec.id).split('.')[-1]

    @api.model
    def get_portal_selections(self, department_id):
        ref = self.env.ref
        ticket_type_valid_ids = [
            ref('dat_website_helpdesk.ticket_type_1').id,
            ref('dat_website_helpdesk.ticket_type_2').id,
            ref('dat_website_helpdesk.ticket_type_3').id,
            ref('dat_website_helpdesk.ticket_type_4').id,
            ref('dat_website_helpdesk.ticket_type_5').id,
            ref('dat_website_helpdesk.ticket_type_6').id,
        ]

        return self.search([('id', 'in', ticket_type_valid_ids)]).mapped(lambda e: (e.code, e.name))
