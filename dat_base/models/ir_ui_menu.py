from odoo import models, api


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    @api.returns('self')
    def get_user_roots(self):
        """ Return all root menu ids visible for the user, but only for whitelist items.

        :return: the root menu ids
        :rtype: list(int)
        """

        base_whitelist = [
            'stock.menu_stock_root',
            'dat_base.dat_menu_quotation',
            'dat_website_helpdesk.menu_helpdesk',
            'dat_dashboard.menu_dashboard',
        ]
        admin_extra = [
            'base.menu_management',
            'base.menu_administration',
            'website.menu_website_configuration',
            'hr.menu_hr_root',
            'contacts.menu_contacts',
            'dat_website_helpdesk.menu_dat_opportunity_root',
            'hr_holidays.menu_hr_holidays_root',
            'dat_zalo_zns.menu_zalo_zns_root',
            'dms.main_menu_dms',
        ]

        xml_ids = list(base_whitelist)
        if self.env.user.has_group('dat_website_helpdesk.helpdesk_admin'):
            xml_ids += admin_extra

        menu_ids = []
        for xml_id in xml_ids:
            menu = self.env.ref(xml_id, raise_if_not_found=False)
            if menu:
                menu_ids.append(menu.id)

        return self.search([('parent_id', '=', False), ('id', 'in', menu_ids)])

