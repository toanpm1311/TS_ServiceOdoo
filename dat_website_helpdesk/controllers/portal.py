import base64
from odoo import _, http
from odoo.addons.portal.controllers import portal
from odoo.http import request
from odoo.osv import expression
from odoo.osv.expression import OR
from werkzeug.utils import redirect
import logging


class TicketPortal(portal.CustomerPortal):
    _items_per_page = 30

    def _prepare_home_portal_values(self, counters):
        """
        Prepare values for the home portal, including ticket count. Args:
        counters (dict): A dictionary containing counters for various portal
        information. Returns: dict: A dictionary of values for the home portal.
        """
        values = super()._prepare_home_portal_values(counters)
        if 'ticket_count' in counters:
            ticket_count = request.env['ticket.helpdesk'].search_count(
                self._get_tickets_domain()) if request.env[
                'ticket.helpdesk'].check_access_rights(
                'read', raise_exception=False) else 0
            values['ticket_count'] = ticket_count
        return values

    def _get_tickets_domain(self):
        """
        Define the domain for searching tickets related to the current customer.
        Returns:
            list: A list representing the domain for ticket search.
        """
        return [('customer_id', '=', request.env.user.partner_id.id)]

    def _get_sale_orders_domain(self):
        """
        Define the domain for searching sale orders related to the current customer.
        """
        return [('partner_id', '=', request.env.user.partner_id.id)]

    def _get_products_domain(self):
        """
        Define the domain for searching products (stock.lot) related to the current user's company.
        """
        return [('buyer_id', '=', request.env.user.partner_id.id)]

    def _get_files_domain(self):
        """
        Define the domain for searching dms.file accessible by the current portal user.
        This checks if the user's partner is in the access groups of the file.
        """
        return []

    def _ticket_get_searchbar_inputs(self):
        values = {
            'name': {'input': 'name', 'label': _('Search in Name'), 'order': 1},
            'subject': {'input': 'subject', 'label': _('Search in Subject'), 'order': 2}
        }
        return dict(sorted(values.items(), key=lambda item: item[1]["order"]))

    def _ticket_get_search_domain(self, search_in, search):
        if search:
            search = search.strip()

        if not search:
            return []
        domain = []
        if search_in == 'name':
            domain = [('name', 'ilike', search)]
        elif search_in == 'subject':
            domain = [('subject', 'ilike', search)]
        elif search_in == 'all':
            domain = ['|', ('name', 'ilike', search), ('subject', 'ilike', search)]

        return domain

    def _sale_order_get_searchbar_inputs(self):
        return {
            'all': {'input': 'all', 'label': _('Search in All'), 'order': 1},
            'name': {'input': 'name', 'label': _('Search in Order #'), 'order': 2},
            'subject': {'input': 'subject', 'label': _('Search in Subject'), 'order': 3},
        }

    def _sale_order_get_search_domain(self, search_in, search):
        search_domain = []
        if search:
            search = search.strip()

        if not search:
            return search_domain

        if search_in == 'name':
            search_domain.append([('name', 'ilike', search)])
        elif search_in == 'subject':
            search_domain.append([('ticket_id.subject', 'ilike', search)])
        elif search_in == 'all':
            return OR([
                [('name', 'ilike', search)],
                [('ticket_id.subject', 'ilike', search)]
            ])

        return OR(search_domain) if search_domain else []

    def _product_get_searchbar_inputs(self):
        return {
            'all': {'input': 'all', 'label': _('Search in All'), 'order': 1},
            'lot_name': {'input': 'lot_name', 'label': _('Search in Lot/Serial #'), 'order': 2},
            'product_name': {'input': 'product_name', 'label': _('Search in Product Name'), 'order': 3},
            'product_ref': {'input': 'product_ref', 'label': _('Search in Product ID'), 'order': 4},
        }

    def _product_get_search_domain(self, search_in, search):
        domain = []

        if search:
            search = search.strip()

        if not search:
            return domain

        if search_in == 'lot_name':
            domain.append([('name', 'ilike', search)]) # Lot/Serial Number (stock.lot.name)
        elif search_in == 'product_name':
            domain.append([('product_id.name', 'ilike', search)]) # Product Name (product.template.name via product.product)
        elif search_in == 'product_ref':
            domain.append([('product_id.default_code', 'ilike', search)]) # Product ID (product.template.default_code via product.product)
        elif search_in == 'all':
            return OR([
                [('name', 'ilike', search)], # Lot/Serial #
                [('product_id.name', 'ilike', search)], # Product Name
                [('product_id.default_code', 'ilike', search)], # Product ID
            ])
        return OR(domain) if domain else []

    def _file_get_searchbar_inputs(self):
        return {
            'all': {'input': 'all', 'label': _('Search in All'), 'order': 1},
            'name': {'input': 'name', 'label': _('Search in file Name'), 'order': 2},
            'category': {'input': 'category', 'label': _('Search in Category'), 'order': 3},
        }

    def _file_get_search_domain(self, search_in, search):
        domain = []

        if search:
            search = search.strip()

        if not search:
            return domain

        if search_in == 'name':
            domain.append([('name', 'ilike', search)])
        elif search_in == 'category':
            domain.append([('category_id.name', 'ilike', search)])
        elif search_in == 'all':
            return OR([[('name', 'ilike', search)], [('category_id.name', 'ilike', search)]])
        return OR(domain) if domain else []

    @http.route(['/my/tickets', '/my/tickets/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_tickets(self, page=1, search=None, search_in='name', filterby=None, **kw):
        """
        Route to display the tickets associated with the current customer.
        Returns:
            http.Response: The HTTP response rendering the tickets page.
        """
        values = self._prepare_my_tickets_values(
            page, search, search_in, filterby)

        # pager
        pager = portal.pager(**values['pager'])

        # content according to pager and archive selected
        tickets = values['tickets'](pager['offset'])
        request.session['my_tickets_history'] = tickets.ids[:100]

        searchbar_inputs = self._ticket_get_searchbar_inputs()
        values = {
            'default_url': "/my/tickets",
            'tickets': tickets,
            'page_name': 'ticket',
            'searchbar_inputs': searchbar_inputs,
            'search_in': search_in,
            'search': search,
            'pager': pager,
        }
        return request.render("dat_website_helpdesk.portal_my_tickets", values)

    def _prepare_my_tickets_values(self, page, search, search_in, filterby, domain=None, url="/my/tickets"):
        values = self._prepare_portal_layout_values()
        ticket_model = request.env['ticket.helpdesk']

        domain = expression.AND([
            domain if domain is not None else [],
            self._get_tickets_domain(),
            self._ticket_get_search_domain(search_in, search)
        ])

        values.update({
            # content according to pager and archive selected
            # lambda function to get the tickets recordset when the pager will be defined in the main method of a route
            'tickets': lambda pager_offset: (
                ticket_model.search(
                    domain, limit=self._items_per_page, offset=pager_offset, order="id desc")
                if ticket_model.check_access_rights('read', raise_exception=False) else
                ticket_model
            ),
            'page_name': 'invoice',
            'pager': {  # vals to define the pager.
                "url": url,
                "total": ticket_model.search_count(domain) if ticket_model.check_access_rights('read', raise_exception=False) else 0,
                "page": page,
                "step": self._items_per_page,
            },
            'default_url': url,
            'filterby': filterby,
        })
        return values

    def _prepare_my_sale_orders_values(self, page, search, search_in, filterby, domain=None, url="/my/sale-orders"):
        values = self._prepare_portal_layout_values()
        sale_order = request.env['sale.order']

        domain_search = self._sale_order_get_search_domain(search_in, search)
        domain_user = self._get_sale_orders_domain()
        domain_status = [('status', '!=', 'draft')]

        current_domain = expression.AND([
            domain if domain is not None else [],
            domain_user,
            domain_search,
            domain_status
        ])

        can_read_so = sale_order.check_access_rights('read', raise_exception=False)

        values.update({
            'sale_orders': lambda pager_offset: (
                sale_order.sudo().search(current_domain, limit=self._items_per_page, offset=pager_offset)
                if can_read_so else request.env['sale.order']
            ),
            'page_name': 'sale_order',
            'pager': {
                "url": url,
                "total": sale_order.sudo().search_count(current_domain) if can_read_so else 0,
                "page": page,
                "step": self._items_per_page,
            },
            'default_url': url,
            'filterby': filterby,
            'searchbar_inputs': self._sale_order_get_searchbar_inputs(),
            'search_in': search_in,
            'search': search,
        })
        return values

    @http.route(['/my/sale-orders', '/my/sale-orders/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_sale_orders(self, page=1, search=None, search_in='all', filterby=None, **kw):
        values = self._prepare_my_sale_orders_values(page, search, search_in, filterby)

        pager = portal.pager(**values['pager'])
        sale_orders = values['sale_orders'](pager['offset'])
        request.session['my_sale_orders_history'] = sale_orders.ids[:100]

        values.update({
            'sale_orders': sale_orders,
            'pager': pager,
            # page_name is already set in _prepare_my_sale_orders_values
        })
        return request.render("dat_website_helpdesk.portal_my_sale_orders_list", values)

    def _prepare_my_products_values(self, page, search, search_in, filterby, domain=None, url="/my/products"):
        values = self._prepare_portal_layout_values()
        stock_lot_model = request.env['stock.lot']

        domain_search = self._product_get_search_domain(search_in, search)
        domain_user = self._get_products_domain()

        current_domain = expression.AND([
            domain if domain is not None else [],
            domain_user,
            domain_search
        ])

        can_read_sl = stock_lot_model.check_access_rights('read', raise_exception=False)

        values.update({
            'products': lambda pager_offset: (
                stock_lot_model.search(current_domain, limit=self._items_per_page, offset=pager_offset)
                if can_read_sl else stock_lot_model
            ),
            'page_name': 'product', # Used for breadcrumbs and active menu
            'pager': {
                "url": url,
                "total": stock_lot_model.search_count(current_domain) if can_read_sl else 0,
                "page": page,
                "step": self._items_per_page,
            },
            'default_url': url,
            'filterby': filterby,
            'searchbar_inputs': self._product_get_searchbar_inputs(),
            'search_in': search_in,
            'search': search,
        })
        return values

    @http.route(['/my/products', '/my/products/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_products(self, page=1, search=None, search_in='all', filterby=None, **kw):
        values = self._prepare_my_products_values(page, search, search_in, filterby)

        pager = portal.pager(**values['pager'])
        products = values['products'](pager['offset']) # This is a lambda, call it with offset
        request.session['my_products_history'] = products.ids[:100]

        values.update({
            'products': products,
            'pager': pager,
        })
        return request.render("dat_website_helpdesk.portal_my_products_list", values)

    def _prepare_my_libraries_values(self, page, search, search_in, filterby, domain=None, url="/my/lib"):
        values = self._prepare_portal_layout_values()
        file_model = request.env['dms.file']

        domain_search = self._file_get_search_domain(search_in, search)
        domain_user = self._get_files_domain()

        current_domain = expression.AND([
            domain if domain is not None else [],
            domain_user,
            domain_search
        ])

        can_read_dir = file_model.check_access_rights('read', raise_exception=False)

        values.update({
            'files': lambda pager_offset: (
                file_model.search(current_domain, limit=self._items_per_page, offset=pager_offset)
                if can_read_dir else file_model
            ),
            'page_name': 'library', # Used for breadcrumbs and active menu
            'pager': {
                "url": url,
                "total": file_model.search_count(current_domain) if can_read_dir else 0,
                "page": page,
                "step": self._items_per_page,
            },
            'default_url': url,
            'filterby': filterby,
            'searchbar_inputs': self._file_get_searchbar_inputs(),
            'search_in': search_in,
            'search': search,
        })
        return values

    @http.route(['/my/lib', '/my/lib/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_libraries(self, page=1, search=None, search_in='all', filterby=None, **kw):
        values = self._prepare_my_libraries_values(page, search, search_in, filterby)

        pager = portal.pager(**values['pager'])
        files = values['files'](pager['offset']) # This is a lambda, call it with offset
        request.session['my_libraries_history'] = files.ids[:100]

        values.update({
            'files': files,
            'pager': pager,
        })
        return request.render("dat_website_helpdesk.portal_my_libraries_list", values)

    @http.route(['/my/lib/file/<int:file_id>'], type='http', auth="user", website=True)
    def portal_my_library_file_detail(self, file_id, access_token=None, **kw):
        """
        Route to display the details and preview of a specific dms.file.
        Args:
            file_id (int): The ID of the dms.file to display.
            access_token (str, optional): Access token for the file.
        Returns:
            http.Response: The HTTP response rendering the file detail page.
        """
        try:
            # Search for the file as the current user.
            # The search method applies DMS security rules (ir.rules).
            dms_file_record = request.env['dms.file'].search([('id', '=', file_id)], limit=1)
            if not dms_file_record:
                logging.warning(f"Access denied or file not found for dms.file ID {file_id} for user {request.env.uid}.")
                return request.redirect('/my/lib')

        except Exception as e:
            logging.error(f"Error accessing dms.file ID {file_id}: {e}")
            return request.redirect('/my/lib')

        # Prepare values for the template
        values = self._prepare_portal_layout_values()
        
        file_content_preview = None
        if dms_file_record.mimetype and dms_file_record.mimetype.startswith('text/'):
            try:
                # content field in dms.file is base64 encoded
                file_content_preview = base64.b64decode(dms_file_record.content or b'').decode('utf-8')
            except Exception:
                file_content_preview = _("Cannot decode text content.")
        
        values.update({
            'dms_file': dms_file_record,
            'page_name': 'library',  # For breadcrumbs and active menu
            'file_content_preview': file_content_preview,
            'access_token': access_token or dms_file_record.access_token, # For download/preview links
        })

        return request.render("dat_website_helpdesk.portal_my_library_file_detail_page", values)

    def _get_product_lot_access_domain(self, lot_id):
        """
        Returns the domain to check access for a specific stock.lot.
        Ensures the lot_id matches and the user has general access via _get_products_domain.
        """
        base_domain = self._get_products_domain()
        return expression.AND([
            [('id', '=', lot_id)],
            base_domain
        ])

    @http.route(['/my/products/<int:lot_id>'], type='http', auth="user", website=True)
    def portal_my_product_detail(self, lot_id, access_token=None, report_type=None, download=False, **kw):
        try:
            product_lot_sudo = request.env['stock.lot'].sudo().search(self._get_product_lot_access_domain(lot_id), limit=1)
            if not product_lot_sudo:
                return request.redirect('/my/products')
        except Exception:
            return request.redirect('/my/products')

        values = self._prepare_portal_layout_values()
        values.update({
            'product_lot': product_lot_sudo,
            'page_name': 'product', 
            'report_type': report_type,
        })

        return request.render("dat_website_helpdesk.portal_my_product_detail_page", values)

    @http.route(['/my/tickets/create'], type='http', auth="user", website=True)
    def create_my_ticket(self, **kwargs):
        """
        Route to create new ticket.
        """
        root_company = request.env.ref('base.main_company')
        branches = request.env['res.company'].sudo().search([('parent_id', '=', root_company.id)])
        departments = request.env['hr.department'].search([])
        states = request.env['res.country.state'].search([('country_id', '=', request.env.ref('base.vn').id)])
        ticket_types = request.env['helpdesk.type'].search([])

        values = {
            'page_name': 'create_ticket',
            'branches': branches,
            'departments': departments,
            'states': states,
            'ticket_types': ticket_types,
            'error_products': [],
        }
        return request.render("dat_website_helpdesk.portal_create_ticket", values)

    @http.route(['/my/tickets/<int:ticket_id>'], type='http', auth="user", website=True)
    def portal_ticket_details(self, ticket_id, **kw):
        """
        Route to display the details of a specific ticket.
        Args:
            ticket_id (int): The ID of the ticket to be displayed (from route).
        Returns:
            http.Response: The HTTP response rendering the ticket details page.
        """
        try:
            # Domain for access check: ensure the ticket ID matches and belongs to the current user's partner
            ticket_domain = expression.AND([
                [('id', '=', ticket_id)],
                self._get_tickets_domain()  # This method returns [('customer_id', '=', request.env.user.partner_id.id)]
            ])
            ticket_record = request.env['ticket.helpdesk'].sudo().search(ticket_domain, limit=1)

            if not ticket_record:
                # If no record found (either doesn't exist or user does not have access), redirect to tickets list
                return request.redirect('/my/tickets')
        except Exception:
            # In case of any other error, redirect to tickets list. Consider logging the error.
            return request.redirect('/my/tickets')

        messages = self._get_ticket_messages(ticket_record)

        values = self._prepare_portal_layout_values()  # Prepare base portal values
        values.update({
            'details': ticket_record,  # The template "portal_ticket_details" expects the ticket object as 'details'
            'page_name': 'ticket',
            'ticket': True,  # Used by breadcrumbs to make "Helpdesk Tickets" a link
            'messages': messages,  # Thêm messages vào context
        })
        return request.render("dat_website_helpdesk.portal_ticket_details", values)

    def _get_ticket_messages(self, ticket_record):
        """
        Get messages from ticket chatter.
        Args:
            ticket_record: ticket.helpdesk recordset
        Returns:
            mail.message recordset: Messages related to the ticket
        """
        messages = request.env['mail.message'].sudo().search([
            ('res_id', '=', ticket_record.id),
            ('model', '=', 'ticket.helpdesk'),
        ], order='create_date desc')

        return messages

    @http.route('/my/tickets/download/<id>', auth='public',
                type='http',
                website=True)
    def ticket_download_portal(self, **kwargs):
        """
        Route to download a PDF version of a specific ticket.
        Args:
            ticket (str): The ID of the ticket to be downloaded.
        Returns:
            http.Response: The HTTP response with the PDF file for download.
        """
        ticket_id = int(kwargs.get('id'))
        data = {
            'help': request.env['ticket.helpdesk'].sudo().browse(ticket_id)}
        report = request.env.ref(
            'dat_website_helpdesk.report_ticket')
        pdf, _ = report.sudo()._render_qweb_pdf(
            report, res_ids=ticket_id, data=data)
        pdf_http_headers = [('Content-Type', 'application/pdf'),
                            ('Content-Length', len(pdf)),
                            ('Content-Disposition',
                             'attachment; filename="Helpdesk Ticket.pdf"')]
        return request.make_response(pdf, headers=pdf_http_headers)

    def _document_check_access(self, model_name, document_id, access_token=None):
        """
        Override _document_check_access để bypass company restriction cho sale.order
        """
        if model_name == 'sale.order':
            return self._sale_order_check_access(document_id, access_token)
        else:
            return super()._document_check_access(model_name, document_id, access_token)

    def _sale_order_check_access(self, order_id, access_token=None):
        """
        Custom access check cho sale.order - bypass company restriction
        """
        order_sudo = request.env['sale.order'].sudo()
        order_sudo = order_sudo.with_context(
            allowed_company_ids=request.env['res.company'].sudo().search([]).ids
        )

        if access_token:
            order = order_sudo.search([
                ('id', '=', order_id),
                ('access_token', '=', access_token)
            ], limit=1)
        else:
            if request.env.user._is_public():
                logging.warning(_("Access denied"))

            order = order_sudo.search([
                ('id', '=', order_id),
                ('partner_id', '=', request.env.user.partner_id.id)
            ], limit=1)

        if not order:
            logging.warning(_("This document does not exist or has been deleted."))

        if not order.access_token:
            order._portal_ensure_token()

        return order

    @http.route(['/my/orders/<int:order_id>/decline'], type='http', auth="public", methods=['POST'], website=True)
    def portal_quote_decline(self, order_id, access_token=None, decline_message=None, **kwargs):
        try:
            order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)

            result = super().portal_quote_decline(order_id, access_token, decline_message, **kwargs)

            if decline_message:
                order_sudo.write({
                    'status': 'rejected',
                    'reject_reason': decline_message
                })

            return result

        except Exception:
            return super().portal_quote_decline(order_id, access_token, decline_message, **kwargs)

    @http.route(['/my/orders/<int:order_id>/accept'], type='json', auth="public", website=True)
    def portal_quote_accept(self, order_id, access_token=None, name=None, signature=None, **kwargs):

        result = super().portal_quote_accept(order_id, access_token, name, signature, **kwargs)
        order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)
        order_sudo.write({'status': 'confirmed'})

        return result

    @http.route(['/my/products/list'], type='json', auth="user", website=True)
    def get_user_products(self, **kwargs):
        try:
            domain = self._get_products_domain()
            products = request.env['stock.lot'].search(domain)
            result = []
            for product in products:
                result.append({
                    'id': product.id,
                    'serial_number': product.name,
                    'product_name': product.product_id.display_name if product.product_id else '',
                })
            return {'success': True, 'products': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}
