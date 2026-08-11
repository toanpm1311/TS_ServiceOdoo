from odoo import http
from odoo.http import request


class DynamicDashboard(http.Controller):
    """Class to search and filter values in dashboard"""

    @http.route('/custom_dashboard/search_input_chart', type='json',
                auth="public", website=True)
    def dashboard_search_input_chart(self, search_input):
        """Function to filter search input in dashboard"""
        return request.env['dashboard.block'].search([
            ('name', 'ilike', search_input)]).ids
