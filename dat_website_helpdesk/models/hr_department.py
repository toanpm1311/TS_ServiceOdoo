from odoo import api, fields, models, _


class Department(models.Model):
    _name = 'hr.department'
    _inherit = ['hr.department', 'abstract.uuid']

    complete_name = fields.Char(store=False)

    @api.model
    def get_portal_selections(self, branch_id):
        ref = self.env.ref
        allowed_department_ids = [
            ref('dat_website_helpdesk.dep_automation_mb').id,
            ref('dat_website_helpdesk.dep_automation_mt').id,
            ref('dat_website_helpdesk.dep_automation_mn').id,
            ref('dat_website_helpdesk.dep_energy_mb').id,
            ref('dat_website_helpdesk.dep_energy_mt').id,
            ref('dat_website_helpdesk.dep_energy_mn').id
        ]

        departments = self.search([
            ('id', 'in', allowed_department_ids),
            ('company_id', '=', int(branch_id))
        ])
        return self.name_search(args=[('id', 'in', departments.ids)])

    @api.depends('name', 'company_id.name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.name} - {record.company_id.name}" if record.company_id else record.name
