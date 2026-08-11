from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """Inheriting the res config settings model"""
    _inherit = 'res.config.settings'

    product_website = fields.Boolean(string="Product On Website",
                                     config_parameter='dat_website_helpdesk.product_website',
                                     help='Product on website')
    auto_close_ticket = fields.Boolean(string="Auto Close Ticket",
                                       config_parameter='dat_website_helpdesk.auto_close_ticket',
                                       help='Auto Close ticket')
    no_of_days = fields.Integer(string="No Of Days",
                                config_parameter='dat_website_helpdesk.no_of_days',
                                help='No of Days')

    reply_template_id = fields.Many2one('mail.template',
                                        domain="[('model', '=', 'ticket.helpdesk')]",
                                        config_parameter='dat_website_helpdesk.reply_template_id',
                                        help='Reply Template of the helpdesk'
                                             ' ticket.')
    helpdesk_menu_show = fields.Boolean('Helpdesk Menu',
                                        config_parameter=
                                        'dat_website_helpdesk.helpdesk_menu_show',
                                        help='Helpdesk menu')
