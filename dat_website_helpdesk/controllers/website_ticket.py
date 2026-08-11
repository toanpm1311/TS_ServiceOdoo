from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import Website


class WebsiteDesk(http.Controller):
    @http.route(['/helpdesk_ticket'], type='http', auth="public", website=True,
                sitemap=True)
    def helpdesk_ticket(self, **kwargs):
        """
        Route to display the helpdesk ticket creation form.
        Returns:
            http.Response: The HTTP response rendering the helpdesk ticket form.
        """
        types = request.env['helpdesk.type'].sudo().search([])
        product = request.env['product.template'].sudo().search([])
        values = {}
        values.update({
            'types': types,
            'product_website': product
        })
        return request.render('dat_website_helpdesk.ticket_form', values)

    @http.route(['/rating/<int:ticket_id>'], type='http', auth="public",
                website=True,
                sitemap=True)
    def rating(self, ticket_id):
        """
        Route to display the rating form for a specific ticket. Args:
        ticket_id (int): The ID of the ticket for which the rating form is
        displayed. Returns: http.Response: The HTTP response rendering the
        rating form.
        """
        ticket = request.env['ticket.helpdesk'].browse(ticket_id)
        data = {
            'ticket': ticket.id,
        }
        return request.render('dat_website_helpdesk.rating_form', data)

    @http.route(['/rating/<int:ticket_id>/submit'], type='http', auth="public",
                website=True, csrf=False,
                sitemap=True)
    def rating_backend(self, ticket_id, **post):
        ticket = request.env['ticket.helpdesk'].sudo().browse(ticket_id).exists()
        if ticket:
            ticket._save_customer_rating(
                post.get('rating'),
                post.get('message'),
            )
        return request.render('dat_website_helpdesk.rating_thanks')


class CustomHomepage(Website):
    @http.route('/', type='http', auth="public", website=True, sitemap=True)
    def index(self, **kw):
        """
        Overrides the default homepage route.
        If the user is not logged in (public user), it renders a custom homepage.
        Otherwise, it calls the original index method to display the standard homepage.
        """
        if request.env.user._is_public():
            return request.render('dat_website_helpdesk.public_homepage', {})
        return super(CustomHomepage, self).index(**kw)
