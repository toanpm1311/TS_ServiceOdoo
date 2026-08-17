from odoo import api, models
from odoo.osv import expression


SALE_DEPARTMENT_XMLIDS = (
    'dat_website_helpdesk.dep_sale_mb',
    'dat_website_helpdesk.dep_sale_mt',
    'dat_website_helpdesk.dep_sale_mn',
)
HELPDESK_SALESPERSON_LIST_FIELDS = {
    'company_id',
    'department_id',
    'display_name',
    'id',
    'job_id',
    'name',
    'work_email',
    'work_phone',
}


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def _helpdesk_salesperson_domain(self):
        """Limit the cross-company selector to active sales employees."""
        departments = [
            department
            for xmlid in SALE_DEPARTMENT_XMLIDS
            if (department := self.env.ref(xmlid, raise_if_not_found=False))
        ]
        return [
            ('active', '=', True),
            ('department_id', 'in', [department.id for department in departments]),
        ]

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        if not self.env.context.get('helpdesk_salesperson_selector'):
            return super()._name_search(name, domain, operator, limit, order)

        salesperson_domain = expression.AND([
            domain or [],
            self._helpdesk_salesperson_domain(),
        ])
        return super(HrEmployee, self.sudo())._name_search(
            name,
            salesperson_domain,
            operator,
            limit,
            order,
        )

    @api.model
    def web_search_read(
        self,
        domain,
        specification,
        offset=0,
        limit=None,
        order=None,
        count_limit=None,
    ):
        use_cross_company_selector = (
            self.env.context.get('helpdesk_salesperson_selector')
            and set(specification).issubset(HELPDESK_SALESPERSON_LIST_FIELDS)
        )
        if not use_cross_company_selector:
            return super().web_search_read(
                domain,
                specification,
                offset=offset,
                limit=limit,
                order=order,
                count_limit=count_limit,
            )

        salesperson_domain = expression.AND([
            domain or [],
            self._helpdesk_salesperson_domain(),
        ])
        return super(HrEmployee, self.sudo()).web_search_read(
            salesperson_domain,
            specification,
            offset=offset,
            limit=limit,
            order=order,
            count_limit=count_limit,
        )
