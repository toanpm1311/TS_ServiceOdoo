from odoo import api, fields, models


class HrEmployee(models.Model):
    """
    Odoo fields was used for SAP includes:
    - name: FullName
    - job_title: Title
    - mobile_phone: EmpPhone
    - work_email: Email
    - company_id: Computed from company_id (Branch)
    """
    _name = 'hr.employee'
    _inherit = ['hr.employee', 'abstract.custom.view']

    # SAP fields
    sap_hr_code = fields.Char("SAP HR Code")
    sap_slp_code = fields.Integer("SAP Slp Code")
    sap_position_hr = fields.Char("SAP Position HR")
    sap_department_hr = fields.Char("SAP Department HR")
    sap_work_shift = fields.Integer("SAP Workshift")
    sap_business_area = fields.Char("SAP Business Area")
    sap_user_name = fields.Char("SAP Username")
    sap_branch = fields.Char("SAP Branch")
    company_id = fields.Many2one('res.company', compute='_compute_company_id', required=True)
    sap_update_date = fields.Datetime(string="Update Date")
    department_id = fields.Many2one('hr.department', 'Department', compute='_compute_department_id', store=True,
                                    readonly=False,
                                    check_company=True)

    @api.depends('sap_branch')
    def _compute_company_id(self):
        for rec in self:
            value = rec.sap_branch
            if not value:
                continue
            if value == "Primary":
                rec.company_id = self.env.ref('dat_website_helpdesk.dat_company_mn')
            elif value == "HN":
                rec.company_id = self.env.ref('dat_website_helpdesk.dat_company_mb')
            elif value == "CT":
                rec.company_id = self.env.ref('dat_website_helpdesk.dat_company_mt')
            else:
                rec.company_id = self.env.ref('base.main_company')

    @api.depends('sap_position_hr', 'sap_department_hr', 'company_id')
    def _compute_department_id(self):
        company_map = {
            self.env.ref('dat_website_helpdesk.dat_company_mb').id: {
                'cs': self.env.ref('dat_website_helpdesk.dep_customer_service_mb').id,
                'automation': self.env.ref('dat_website_helpdesk.dep_automation_mb').id,
                'energy': self.env.ref('dat_website_helpdesk.dep_energy_mb').id,
                'sale': self.env.ref('dat_website_helpdesk.dep_sale_mb').id
            },
            self.env.ref('dat_website_helpdesk.dat_company_mt').id: {
                'cs': self.env.ref('dat_website_helpdesk.dep_customer_service_mt').id,
                'automation': self.env.ref('dat_website_helpdesk.dep_automation_mt').id,
                'energy': self.env.ref('dat_website_helpdesk.dep_energy_mt').id,
                'sale': self.env.ref('dat_website_helpdesk.dep_sale_mt').id
            },
            self.env.ref('dat_website_helpdesk.dat_company_mn').id: {
                'cs': self.env.ref('dat_website_helpdesk.dep_customer_service_mn').id,
                'automation': self.env.ref('dat_website_helpdesk.dep_automation_mn').id,
                'energy': self.env.ref('dat_website_helpdesk.dep_energy_mn').id,
                'sale': self.env.ref('dat_website_helpdesk.dep_sale_mn').id
            }
        }

        for record in self:

            company_departments = company_map.get(record.company_id.id)
            if not company_departments:
                record.department_id = False
                continue

            department_id = False
            pos_lower = (record.sap_position_hr or '').lower()
            dep_lower = (record.sap_department_hr or '').lower()

            if 'tt dịch vụ' in dep_lower:
                department_id = company_departments['cs']
            elif 'kinh doanh' in pos_lower:
                department_id = company_departments['sale']
            elif 'kỹ thuật' in pos_lower:
                if 'nl' in dep_lower:
                    department_id = company_departments['energy']
                elif 'tđh' in dep_lower:
                    department_id = company_departments['automation']

            if department_id:
                record.department_id = department_id

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._compute_company_id()
        employees._compute_department_id()

        main_company = self.env.ref('base.main_company')
        default_group = self.env.ref('base.default_user')
        erp_group = self.env.ref('base.group_erp_manager')

        users_to_create = []

        for employee, vals in zip(employees, vals_list):
            if not employee.user_id and employee.work_email:
                phone_number = employee.mobile_phone
                company = employee.company_id

                user_vals = {
                    'name': employee.name,
                    'login': employee.work_email,
                    'email': employee.work_email,
                    'company_id': company.id,
                    'create_employee_id': employee.id,
                    'create_employee': False,
                    'partner_id': employee.work_contact_id.id,
                    'phone': phone_number,
                    'mobile_phone': phone_number,
                    'company_ids': [(6, 0, [company.id, main_company.id])],
                    'groups_id': [(6, 0, default_group.groups_id.ids + [erp_group.id])],
                }

                users_to_create.append(user_vals)

        if users_to_create:
            self.env['res.users'].create(users_to_create)

        return employees

    def _create_work_contacts(self):
        work_contacts = super()._create_work_contacts()

        for employee in self:
            if employee.work_contact_id:
                employee.work_contact_id.phone = employee.mobile_phone

        return work_contacts
