from odoo import models


class WebsiteMenu(models.Model):
    """Inheriting the website menu"""
    _inherit = "website.menu"

    def _compute_visible(self):
        """Compute function for to  visible the menu based on the boolean
        field visibility"""
        super()._compute_visible()
        show_menu_header = self.env['ir.config_parameter'].sudo().get_param(
            'dat_website_helpdesk.helpdesk_menu_show')
        for menu in self:
            if menu.name == 'Helpdesk' and not show_menu_header:
                menu.is_visible = False
            if menu.name == 'Helpdesk' and show_menu_header:
                menu.is_visible = True
