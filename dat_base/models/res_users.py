from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    sap_hr_code = fields.Char(string='HR Code', compute='_compute_employee_info')
    sap_position_hr = fields.Char(string='Position HR', compute='_compute_employee_info')
    role = fields.Char(string='Role', compute='_compute_role')

    @api.depends('groups_id')
    def _compute_role(self):
        for rec in self:
            rec.role = False
            if self.env.ref('dat_website_helpdesk.helpdesk_user') in rec.groups_id:
                rec.role = "user"
            if self.env.ref('dat_website_helpdesk.helpdesk_admin') in rec.groups_id:
                rec.role = "admin"

    @api.depends('employee_ids')
    def _compute_employee_info(self):
        for rec in self:
            if not rec.employee_ids:
                rec.sap_hr_code = False
                rec.sap_position_hr = False
                continue
            employee = rec.employee_ids[-1]
            rec.sap_hr_code = employee.sap_hr_code
            rec.sap_position_hr = employee.sap_position_hr
