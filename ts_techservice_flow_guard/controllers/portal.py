from odoo.addons.dat_website_helpdesk.controllers.portal import TicketPortal
from odoo.osv import expression


class TsTicketPortal(TicketPortal):

    def _get_sale_orders_domain(self):
        return expression.AND([
            super()._get_sale_orders_domain(),
            [('ts_merged_into_order_id', '=', False)],
        ])
