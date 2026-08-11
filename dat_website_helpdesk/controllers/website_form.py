import base64
import json
from psycopg2 import IntegrityError
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.website.controllers.form import WebsiteForm


class HelpdeskProduct(http.Controller):
    """    Controller for handling helpdesk products.
    """

    @http.route('/product', auth='public', type='json')
    def product(self):
        prols = []
        acc = request.env['product.template'].sudo().search([])
        for i in acc:
            dic = {'name': i['name'],
                   'id': i['id']}
            prols.append(dic)
        return prols


class WebsiteFormTicket(WebsiteForm):
    def _extract_form_value(self, type, fname, default_val, kwargs):
        return type(kwargs.get(fname)) if kwargs.get(fname) else default_val

    def _handle_website_form(self, model_name, **kwargs):
        """
        Handle the submission of website forms.
        :param model_name: The name of the model associated with the form.
        :type model_name: str
        :param kwargs: Keyword arguments containing form data.
        :type kwargs: dict
        :return: JSON response indicating the success or failure of form submission.
        :rtype: str
        """
        if model_name != 'ticket.helpdesk':
            return super()._handle_website_form(model_name, **kwargs)

        customer = request.env.user.partner_id
        ticket_attachment_ids = []
        ticket_attachments = []
        attachment_index = 0
        while f"ticket_attachment[0][{attachment_index}]" in kwargs:
            attachment_key = f"ticket_attachment[0][{attachment_index}]"
            if attachment_key in kwargs:
                attachment = kwargs[attachment_key]
                ticket_attachments.append(attachment)
            attachment_index += 1
        for attachment in ticket_attachments:
            attached_file = attachment.read()
            ticket_attachment_ids.append([0, 0, {
                'name': attachment.filename,
                'type': 'binary',
                'datas': base64.encodebytes(attached_file),
            }])

        technical_solution_attachment_ids = []
        technical_solution_attachments = []
        attachment_index = 0
        while f"technical_solution_attachment[1][{attachment_index}]" in kwargs:
            attachment_key = f"technical_solution_attachment[1][{attachment_index}]"
            if attachment_key in kwargs:
                attachment = kwargs[attachment_key]
                technical_solution_attachments.append(attachment)
            attachment_index += 1
        for attachment in technical_solution_attachments:
            attached_file = attachment.read()
            technical_solution_attachment_ids.append([0, 0, {
                'name': attachment.filename,
                'type': 'binary',
                'datas': base64.encodebytes(attached_file),
            }])

        ticket_type_code = self._extract_form_value(str, 'ticket_type', False, kwargs)
        ticket_type = request.env['helpdesk.type'].sudo().search(
            [('code', '=', ticket_type_code)], limit=1)


        ref = request.env.ref 
        branch_id = self._extract_form_value(int, 'branch', False, kwargs)
        department_id = self._extract_form_value(int, 'department', False, kwargs)

        if ticket_type.id in (
            ref('dat_website_helpdesk.ticket_type_1').id,
            ref('dat_website_helpdesk.ticket_type_2').id,
            ref('dat_website_helpdesk.ticket_type_3').id,
            ref('dat_website_helpdesk.ticket_type_4').id,
        ):
            if branch_id == ref('dat_website_helpdesk.dat_company_mt').id:
                department_id = ref('dat_website_helpdesk.dep_customer_service_mt').id
            elif branch_id== ref('dat_website_helpdesk.dat_company_mb').id:
                department_id = ref('dat_website_helpdesk.dep_customer_service_mb').id
            elif branch_id == ref('dat_website_helpdesk.dat_company_mn').id:
                department_id = ref('dat_website_helpdesk.dep_customer_service_mn').id

        ticket_wizard_vals = {
            'subject': kwargs.get('subject', False),
            'branch': branch_id,
            'state_id': self._extract_form_value(int, 'state', False, kwargs),
            'priority_id': request.env.ref('dat_website_helpdesk.ticket_priority_1').id,
            'delivery_address': kwargs.get('delivery_address', False),
            'department_id': department_id,
            'ticket_type_id': ticket_type.id if ticket_type else False,
            'ir_attachment_ids': ticket_attachment_ids,
            'requestor': customer.id,
            'requestor_from_portal': kwargs.get('contact_person', False),
            'requestor_phone_from_portal': kwargs.get('contact_phone', False),
            'origin_sale_order': kwargs.get('origin_sale_order', False),
            'install_address': kwargs.get('install_address', False),
            'note': kwargs.get('note', False),
            'technical_solution_attachment_ids': technical_solution_attachment_ids,
            'technical_solution_note': kwargs.get('technical_solution_note', False),
            'technical_solution_link': kwargs.get('technical_solution_link', False),
            'materials_supplier': kwargs.get('materials_supplier', False),
            'expected_implementation_date': kwargs.get('expected_implementation_date', False),
            'expected_implementation_address': kwargs.get('expected_implementation_address', False),
            'implementation_note': kwargs.get('implementation_note', False),
        }
                    
        product_count = self._extract_form_value(int, 'product_count', 0, kwargs)
        product_vals_list = []
        if product_count > 0:
            for i in range(product_count):
                product_index = i + 1
                serial_number = kwargs.get(f'serial_number_{product_index}', False)
                stock_lot = request.env['stock.lot'].search(
                    [('name', '=', serial_number)], limit=1)
                if not stock_lot:
                    raise ValidationError(_(
                        "Không tìm thấy số serial %s trên TechService. Vui lòng đồng bộ serial trước khi tạo phiếu."
                    ) % (serial_number or ''))
                if not stock_lot.owner_id or not stock_lot.buyer_id:
                    raise ValidationError(_(
                        "Số serial %s chưa có khách hàng/người sở hữu. Vui lòng đồng bộ lại serial trước khi tạo phiếu."
                    ) % serial_number)
                error_description = kwargs.get(f'error_description_{product_index}', False)
                error_note = kwargs.get(f'error_note_{product_index}', False)

                product_attachment_ids = []
                product_attachments = []
                attachment_index = 0
                while f"product_attachment[{i + 2}][{attachment_index}]" in kwargs:
                    attachment_key = f"product_attachment[{i + 2}][{attachment_index}]"
                    if attachment_key in kwargs:
                        attachment = kwargs[attachment_key]
                        product_attachments.append(attachment)
                    attachment_index += 1
                for attachment in product_attachments:
                    attached_file = attachment.read()
                    product_attachment_ids.append([0, 0, {
                        'name': attachment.filename,
                        'type': 'binary',
                        'datas': base64.encodebytes(attached_file),
                    }])

                product_vals_list.append({
                    'serial_number': stock_lot.id,
                    'product_id': stock_lot.product_id.id,
                    'owner_id': stock_lot.owner_id.id,
                    'buyer_id': stock_lot.buyer_id.id,
                    'error_description': error_description,
                    'note': error_note,
                    'product_attachment_ids': product_attachment_ids,
                })
        if product_vals_list:
            ticket_wizard_vals['ticket_product_ids'] = [(0, 0, vals) for vals in product_vals_list]
        create_ticket_wizard = request.env['create.ticket.wizard'].sudo().create(
                ticket_wizard_vals)
        ticket_ids = create_ticket_wizard.sudo()._action_create()
        ticket_ids.create_source = 'portal'

        return json.dumps({'id': ticket_ids[0].id})
