from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CreateTicketWizard(models.TransientModel):
    _inherit = 'create.ticket.wizard'

    service_contact_name = fields.Char(string='Người liên hệ')
    service_contact_phone = fields.Char(string='SĐT người liên hệ')

    @api.onchange('ticket_product_ids')
    def _onchange_ticket_product_ids_set_requestor_service_extension(self):
        for wizard in self:
            lines = wizard.ticket_product_ids.filtered('serial_number')
            if len(lines) != 1 or not lines.owner_id:
                continue
            owner = lines.owner_id
            if wizard.requestor != owner:
                wizard.requestor = owner
                wizard.requestor_phone = lines.serial_number.owner_phone or owner.phone or owner.mobile
                wizard.install_address = owner.contact_address
            if not wizard.service_contact_name:
                wizard.service_contact_name = owner.name

    def _validate_before_create(self):
        super()._validate_before_create()
        self._check_remote_warranty_duplicate_products()

    def _action_create(self):
        allowed_tickets = self._get_allowed_previous_remote_warranty_tickets()
        tickets = super()._action_create()
        if allowed_tickets:
            allowed_tickets.write({'allow_next_remote_warranty_ticket': False})
            allowed_tickets.message_post(body=_('Da su dung quyen tao lai bao hanh tu xa mot lan.'))
        return tickets

    def _check_remote_warranty_duplicate_products(self):
        for wizard in self:
            if not wizard._is_remote_warranty_wizard():
                continue
            for line in wizard.ticket_product_ids.filtered('serial_number'):
                if not wizard._is_remote_warranty_product(line):
                    continue
                previous_ticket = wizard._get_previous_remote_warranty_ticket(line.serial_number)
                if previous_ticket and not previous_ticket.allow_next_remote_warranty_ticket:
                    raise ValidationError(_(
                        "Serial %(serial)s da duoc bao hanh tu xa o tac vu %(ticket)s. "
                        "Vui long mo dung tac vu cu va bam 'Cho phep tao lai BH tu xa' truoc khi tao moi."
                    ) % {
                        'serial': line.serial_number.name,
                        'ticket': previous_ticket.name or previous_ticket.display_name,
                    })

    def _get_allowed_previous_remote_warranty_tickets(self):
        allowed_tickets = self.env['ticket.helpdesk']
        for wizard in self:
            if not wizard._is_remote_warranty_wizard():
                continue
            for line in wizard.ticket_product_ids.filtered('serial_number'):
                if not wizard._is_remote_warranty_product(line):
                    continue
                previous_ticket = wizard._get_previous_remote_warranty_ticket(line.serial_number)
                if previous_ticket and previous_ticket.allow_next_remote_warranty_ticket:
                    allowed_tickets |= previous_ticket
        return allowed_tickets

    def _is_remote_warranty_wizard(self):
        self.ensure_one()
        return (
            self.workflow_id == self.env.ref(self.WORKFLOW_1)
            and self.ticket_type_id == self.env.ref('dat_website_helpdesk.ticket_type_3')
        )

    def _is_remote_warranty_product(self, line):
        self.ensure_one()
        warranty_end_date = line.serial_number.warranty_end_date
        return bool(
            warranty_end_date
            and fields.Datetime.to_datetime(warranty_end_date) >= fields.Datetime.now()
        )

    def _get_previous_remote_warranty_ticket(self, serial_number):
        self.ensure_one()
        return self.env['ticket.helpdesk'].sudo().search([
            ('workflow_id', '=', self.env.ref(self.WORKFLOW_1).id),
            ('ticket_type_id', '=', self.env.ref('dat_website_helpdesk.ticket_type_3').id),
            ('stock_lot_id', '=', serial_number.id),
            ('product_warranty_status', '=', 'warranty'),
            ('status', '!=', 'rejected'),
        ], order='create_date desc, id desc', limit=1)

    def _prepare_ticket_vals(self, product=False):
        vals = super()._prepare_ticket_vals(product=product)
        if product and product.buyer_id:
            vals['customer_company_name'] = product.buyer_id.company_name or product.buyer_id.display_name
        if self.service_contact_name:
            vals['customer_contact_name'] = self.service_contact_name
        if self.service_contact_phone:
            vals['customer_phone'] = self.service_contact_phone
        return vals
