import logging
import re
from datetime import datetime

import pytz
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class CreateTicketWizard(models.TransientModel):
    _name = "create.ticket.wizard"
    _description = "Create Ticket Wizard"

    WORKFLOW_1 = 'dat_website_helpdesk.workflow_1'
    WORKFLOW_2 = 'dat_website_helpdesk.workflow_2'
    WORKFLOW_3 = 'dat_website_helpdesk.workflow_3'
    WORKFLOW_4 = 'dat_website_helpdesk.workflow_4'
    WORKFLOW_RETURN = 'dat_website_helpdesk.workflow_return'
    TICKET_TYPE_RETURN = 'dat_website_helpdesk.ticket_type_return'

    subject = fields.Char('Subject', required=True)
    branch = fields.Many2one(
        'res.company',
        string='Branch',
        required=True,
        domain=lambda self: [('id', 'in', self.sudo().env.ref('base.main_company').child_ids.ids)],
        default=lambda self: self._get_default_branch()
    )
    state_id = fields.Many2one("res.country.state", string='State', ondelete='restrict',
                               domain=lambda self: [('country_id', '=', self.env.ref('base.vn').id)])
    priority_id = fields.Many2one('ticket.priority',
                                  string='Priority', required=True,
                                  default=lambda self: self.env['ticket.priority'].search([('default', '=', True)],
                                                                                          limit=1))
    delivery_address = fields.Char(string='Delivery Address')
    note_SO = fields.Char(string='Ghi chú SO')
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True,
        default=lambda self: self._get_default_department()
    )
    department_domain_ids = fields.Many2many(
        'hr.department',
        compute='_compute_department_domain_ids',
        string='Domain Department'
    )
    ticket_type_id = fields.Many2one('helpdesk.type',
                                     string='Ticket Type', required=True)
    ticket_type_id_domain = fields.Binary(string="Ticket Type Domain", compute="_compute_ticket_type_id_domain")
    ir_attachment_ids = fields.Many2many('ir.attachment', string="Upload File")
    note = fields.Char('Note')
    ticket_product_ids = fields.One2many('ticket.product', 'ticket_wizard_id', string='Products',
                                        domain="[('owner_id', '=', requestor)]")
    requestor = fields.Many2one('res.partner', string='Requestor', domain="[('employee_ids', '=', False)]")
    requestor_phone = fields.Char('Requestor Phone', related='requestor.phone', readonly=False)
    requestor_from_portal = fields.Char('Requestor From Portal')
    requestor_phone_from_portal = fields.Char('Requestor From Portal')
    company_name = fields.Char('Company Name')
    workflow_id = fields.Many2one('helpdesk.workflow', string='Workflow',
                                  compute='_compute_workflow_id',
                                  store=True, readonly=True)
    wf_external_id = fields.Char(compute='_compute_workflow_external_id')
    ticket_type_external_id = fields.Char(compute='_compute_ticket_type_external_id')

    origin_sale_order = fields.Char(string='Origin Sale Order')
    install_address = fields.Char(string='Install Address')
    install_note = fields.Text(string='Note')

    # Fields WF4
    technical_solution_attachment_ids = fields.Many2many(
        'ir.attachment',
        'wizard_ticket_helpdesk_technical_solution_attachment_rel',
        'wizard_ticket_id', 'attachment_id',
        string="Technical Solution Attachment"
    )
    technical_solution_note = fields.Text(string='Note')
    technical_solution_link = fields.Char(string='Technical Solution Link')
    materials_supplier = fields.Selection([('dat', 'DAT Internal'), ('customer', 'Customer')], string='Material Supplier')
    expected_implementation_date = fields.Datetime(string='Expected Implementation Date')
    expected_implementation_address = fields.Char(string='Expected Implementation Address')
    implementation_note = fields.Text(string='Implementation Note')

    @api.constrains('ticket_product_ids', 'requestor')
    def _check_owner_id_consistency(self):
        for wizard in self:
            if wizard.ticket_product_ids:
                owner_ids = wizard.ticket_product_ids.mapped('owner_id')
                if len(set(owner_ids.ids)) > 1:
                    raise ValidationError(
                        _(
                            "All owner IDs in ticket products must be the same.\n"
                            "%s"
                        ) % wizard._format_ticket_product_owner_mismatch()
                    )
                if wizard.requestor and wizard.requestor.id not in owner_ids.ids:
                    raise ValidationError(
                        _(
                            "All series must have an owner that matches the requester (%s).\n"
                            "%s"
                        ) % (
                            wizard._format_partner_debug(wizard.requestor),
                            wizard._format_ticket_product_owner_mismatch(),
                        )
                    )

    def _format_ticket_product_owner_mismatch(self):
        self.ensure_one()
        rows = []
        for line in self.ticket_product_ids:
            rows.append(_(
                "- Serial: %(serial)s | Owner: %(owner)s | Buyer: %(buyer)s"
            ) % {
                'serial': line.serial_number.name or '',
                'owner': self._format_partner_debug(line.owner_id),
                'buyer': self._format_partner_debug(line.buyer_id),
            })
        return "\n".join(rows)

    def _format_partner_debug(self, partner):
        self.ensure_one()
        if not partner:
            return _("(empty)")
        card_code = (partner.card_code or '').strip()
        return "[ID:%s%s] %s" % (
            partner.id,
            " / CardCode:%s" % card_code if card_code else "",
            partner.display_name,
        )

    @api.depends('ticket_type_id')
    def _compute_ticket_type_external_id(self):
        for rec in self:
            external_ids = rec.ticket_type_id._get_external_ids()
            external_id = [x.split(".")[1] for x in external_ids.get(rec.ticket_type_id.id, []) if
                           x.split(".")[0] == 'dat_website_helpdesk']
            rec.ticket_type_external_id = external_id[0] if external_id else False

    @api.depends('workflow_id')
    def _compute_workflow_external_id(self):
        for rec in self:
            external_ids = rec.workflow_id._get_external_ids()
            external_id = [x.split(".")[1] for x in external_ids.get(rec.workflow_id.id, []) if
                           x.split(".")[0] == 'dat_website_helpdesk']
            rec.wf_external_id = external_id[0] if external_id else False

    @api.model
    def _get_user_companies(self):
        companies = self.env.user.employee_ids.mapped('company_id')
        leaf_companies = self.env['res.company']

        for company in companies:
            children = self._get_leaf_companies(company)
            if children:
                leaf_companies |= children
            else:
                leaf_companies |= company

        return leaf_companies

    def _get_leaf_companies(self, company):
        if not company.child_ids:
            return self.env['res.company']
        leaf_companies = self.env['res.company']
        for child in company.child_ids:
            if child.child_ids:
                leaf_companies |= self._get_leaf_companies(child)
            else:
                leaf_companies |= child
        return leaf_companies

    @api.depends('branch')
    def _compute_department_domain_ids(self):
        for record in self:
            allowed_department_ids = [
                self.env.ref('dat_website_helpdesk.dep_customer_service_mb').id,
                self.env.ref('dat_website_helpdesk.dep_customer_service_mt').id,
                self.env.ref('dat_website_helpdesk.dep_customer_service_mn').id,
                self.env.ref('dat_website_helpdesk.dep_automation_mb').id,
                self.env.ref('dat_website_helpdesk.dep_automation_mt').id,
                self.env.ref('dat_website_helpdesk.dep_automation_mn').id,
                self.env.ref('dat_website_helpdesk.dep_energy_mb').id,
                self.env.ref('dat_website_helpdesk.dep_energy_mt').id,
                self.env.ref('dat_website_helpdesk.dep_energy_mn').id
            ]

            domain_departments = self.env['hr.department'].search([
                ('id', 'in', allowed_department_ids),
                ('company_id', '=', record.branch.id)
            ])
            record.department_domain_ids = domain_departments

    @api.model
    def _get_default_department(self):
        if self._get_default_branch:
            department_ids = self.env.user.employee_ids.mapped('department_id')
            if len(department_ids) == 1:
                return department_ids.id
        return False

    @api.model
    def _get_default_branch(self):
        companies = self._get_user_companies()
        if len(companies) == 1:
            return companies.id
        return False

    @api.onchange('requestor')
    def _onchange_requestor(self):
        if self.requestor:
            self.requestor_phone = self._partner_phone(self.requestor)
            self.install_address = self.requestor.contact_address
            if self.ticket_product_ids:
                invalid_lines = self.ticket_product_ids.filtered(lambda line: line.owner_id != self.requestor)
                if invalid_lines:
                    self.ticket_product_ids = [(5, 0, 0)]

    @api.onchange('ticket_product_ids')
    def _onchange_ticket_product_ids_set_requestor(self):
        for wizard in self:
            if not wizard.requestor and len(wizard.ticket_product_ids) == 1:
                lines = wizard.ticket_product_ids
                if 'sequence' in self.env['ticket.product']._fields:
                    lines = lines.sorted('sequence')
                first_line = lines[:1]
                if first_line and first_line.owner_id:
                    wizard.requestor = first_line.owner_id
                    wizard.requestor_phone = wizard._serial_phone(first_line.serial_number, 'owner')

    @api.model
    def _partner_phone(self, partner):
        return partner.phone or partner.mobile or False

    @api.model
    def _serial_phone(self, lot, role):
        partner = lot.buyer_id if role == 'buyer' else lot.owner_id
        lot_phone = lot.buyer_phone if role == 'buyer' else lot.owner_phone
        return lot_phone or self._partner_phone(partner)

    def _ticket_customer_phone(self, product=False):
        if self.requestor_phone_from_portal:
            return self.requestor_phone_from_portal
        if product and product.serial_number:
            return (
                self._serial_phone(product.serial_number, 'owner')
                or self._serial_phone(product.serial_number, 'buyer')
            )
        return self.requestor_phone or self._partner_phone(self.requestor)

    @api.onchange('branch')
    def _onchange_branch(self):
        if self.department_id and self.department_id.company_id != self.branch:
            self.department_id = False

    @api.onchange('department_id')
    def _onchange_department(self):
        for record in self:
            ticket_type_valid_ids = record.get_valid_ticket_type()

            if record.ticket_type_id and record.ticket_type_id.id not in ticket_type_valid_ids:
                record.ticket_type_id = False

    @api.depends('department_id')
    def _compute_ticket_type_id_domain(self):
        for record in self:
            valid_ticket_type_ids = record.get_valid_ticket_type()
            record.ticket_type_id_domain = [('id', 'in', valid_ticket_type_ids)]

    @api.depends('ticket_type_id')
    def _compute_workflow_id(self):
        for rec in self:
            if rec.ticket_type_id:
                if rec.ticket_type_id == self.env.ref(self.TICKET_TYPE_RETURN):
                    rec.workflow_id = self.env.ref(self.WORKFLOW_RETURN)
                elif rec.ticket_type_id == self.env.ref('dat_website_helpdesk.ticket_type_4'):
                    rec.workflow_id = self.env.ref(self.WORKFLOW_2)
                elif rec.ticket_type_id == self.env.ref('dat_website_helpdesk.ticket_type_5'):
                    rec.workflow_id = self.env.ref(self.WORKFLOW_3)
                elif rec.ticket_type_id == self.env.ref('dat_website_helpdesk.ticket_type_6'):
                    rec.workflow_id = self.env.ref(self.WORKFLOW_4)
                else:
                    rec.workflow_id = self.env.ref(self.WORKFLOW_1)

    def get_valid_ticket_type(self):
        self.ensure_one()
        service_deps = [
            self.env.ref('dat_website_helpdesk.dep_customer_service_mn').id,
            self.env.ref('dat_website_helpdesk.dep_customer_service_mb').id,
            self.env.ref('dat_website_helpdesk.dep_customer_service_mt').id
        ]
        main_types = [
            self.env.ref('dat_website_helpdesk.ticket_type_1').id,
            self.env.ref('dat_website_helpdesk.ticket_type_2').id,
            self.env.ref('dat_website_helpdesk.ticket_type_3').id,
            self.env.ref('dat_website_helpdesk.ticket_type_4').id,
        ]
        other_types = [
            self.env.ref('dat_website_helpdesk.ticket_type_5').id,
            self.env.ref('dat_website_helpdesk.ticket_type_6').id,
        ]
        if self.department_id.id in service_deps:
            ticket_type_valid_ids = main_types
        else:
            ticket_type_valid_ids = other_types

        hcm_service_department = self.env.ref('dat_website_helpdesk.dep_customer_service_mn')
        if self.department_id == hcm_service_department:
            ticket_type_valid_ids = ticket_type_valid_ids + [self.env.ref(self.TICKET_TYPE_RETURN).id]

        return ticket_type_valid_ids

    def _action_create(self):
        self.ensure_one()
        self._validate_before_create()
        ticket_model = self.env['ticket.helpdesk'].with_context(skip_phone_validation_from_create_ticket_wizard=True)
        ticket_ids = ticket_model
        product_workflows = (
            self.env.ref(self.WORKFLOW_1),
            self.env.ref(self.WORKFLOW_RETURN),
        )
        if self.workflow_id in product_workflows:
            for product in self.ticket_product_ids:
                ticket_vals = self._prepare_ticket_vals(product)
                new_ticket = ticket_model.sudo().create(ticket_vals)
                if not new_ticket:
                    continue
                ticket_ids += new_ticket
        else:
            ticket_vals = self._prepare_ticket_vals()
            new_ticket = ticket_model.sudo().create(ticket_vals)
            if new_ticket:
                ticket_ids += new_ticket
        return ticket_ids

    def action_create(self):
        self.ensure_one()
        try:
            self._action_create()
            return self._return_notification(
                type='success',
                message=_('Create ticket(s) successfully'),
                next_action={'type': 'ir.actions.client', 'tag': 'soft_reload'}
            )

        except (UserError, ValidationError) as e:
            _logger.warning(f"User error: {e}")
            return self._return_reload_wizard_with_notification('warning', str(e))

        except Exception as e:
            _logger.exception("Unexpected error while creating ticket from wizard.")
            return self._return_reload_wizard_with_notification('danger',
                                                                _('An unexpected error occurred:\n%s') % str(e))

    def _validate_before_create(self):
        if self.workflow_id in (self.env.ref(self.WORKFLOW_1), self.env.ref(self.WORKFLOW_RETURN)) \
                and not self.ticket_product_ids:
            raise ValidationError(_("You need to add at least 1 product line to create a ticket."))

        if self.department_id and not self.env['ticket.helpdesk'].get_assigned_user_id_based_on_department(department=self.department_id, branch=self.branch, ticket_type=self.ticket_type_id):
            raise ValidationError(_("Department %s in branch %s does not have a manager assigned. Please assign a manager to this branch before creating a ticket!") % (self.department_id.name, self.branch.name))

    def _prepare_ticket_vals(self, product=False):
        val_list = {
            'customer_phone': self._ticket_customer_phone(product),
            'customer_email': self.requestor.email,
            'customer_address': self.requestor.contact_address,
            'customer_company_name': self.requestor.company_name,
            'subject': self.subject,
            'priority_id': self.priority_id.id,
            'workflow_id': self.workflow_id.id,
            'step_id': self.get_step_id(),
            'note_SO': self.note_SO or self.delivery_address,
            'customer_contact_name': self.requestor_from_portal if self.requestor_from_portal else self.requestor.display_name,
            'branch': self.branch.id,
            'state_id': self.state_id.id,
            'department_id': self.department_id.id,
            'ticket_type_id': self.ticket_type_id.id,
            'ticket_type_id_domain': self.ticket_type_id_domain,
        }
        if self.workflow_id in (self.env.ref(self.WORKFLOW_1), self.env.ref(self.WORKFLOW_RETURN)) and product:
            buyer = product.buyer_id
            owner = product.owner_id
            val_list.update({
                'customer_id': buyer.id,
                'owner_id': owner.id,
                'owner_phone': self._serial_phone(product.serial_number, 'owner'),
                'owner_email': owner.email,
                'owner_address': owner.contact_address,
                'description': product.error_description or self.subject,
                'stock_lot_id': product.serial_number.id,
                'product_error_note': product.note,
                'ticket_product_image_ids': [(6, 0, product.product_attachment_ids.ids)],
            })
            if self.workflow_id == self.env.ref(self.WORKFLOW_RETURN):
                val_list['service_action_invisible'] = True
        elif self.workflow_id in (self.env.ref(self.WORKFLOW_2), self.env.ref(self.WORKFLOW_3), self.env.ref(self.WORKFLOW_4)):
            val_list.update({
                'customer_id': self.requestor.id,
                'owner_id': self.requestor.id,
                'owner_phone': self._partner_phone(self.requestor),
                'owner_email': self.requestor.email,
                'owner_address': self.requestor.contact_address,
                'install_address': self.install_address,
            })
            if self.workflow_id == self.env.ref(self.WORKFLOW_2):
                val_list.update({
                    'install_attachment_ids': [(6, 0, self.ir_attachment_ids.ids)],
                    'description': self.subject,
                    'origin_sale_order': self.origin_sale_order,
                })
            elif self.workflow_id == self.env.ref(self.WORKFLOW_3):
                val_list.update({
                    'ticket_attachment_ids': [(6, 0, self.ir_attachment_ids.ids)],
                    'description': self.note or self.subject,
                })
            elif self.workflow_id == self.env.ref(self.WORKFLOW_4):
                val_list.update({
                    'ticket_attachment_ids': [(6, 0, self.ir_attachment_ids.ids)],
                    'description': self.note or self.subject,
                    'technical_solution_attachment_ids': [(6, 0, self.technical_solution_attachment_ids.ids)],
                    'technical_solution_note': self.technical_solution_note,
                    'technical_solution_link': self.technical_solution_link,
                    'materials_supplier': self.materials_supplier,
                    'expected_implementation_date': self.expected_implementation_date,
                    'expected_implementation_address': self.expected_implementation_address,
                    'implementation_note': self.implementation_note,
                })
        else:
            raise UserError(_('Invalid workflow type.'))
        return val_list

    def _return_notification(self, type, message, next_action=None):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': type,
                'sticky': False,
                'message': message,
                **({'next': next_action} if next_action else {}),
            },
        }

    def _return_reload_wizard_with_notification(self, type, message):
        return self._return_notification(
            type=type,
            message=message,
            next_action={
                'type': 'ir.actions.act_window',
                'name': _('Create Ticket Wizard'),
                'res_model': self._name,
                'res_id': False,
                'view_mode': 'form',
                'view_type': 'form',
                'views': [[False, 'form']],
                'target': 'new',
                'context': dict(self.env.context,
                                **self._get_default_context_from_self()),
            }
        )

    def _get_default_context_from_self(self, exclude_fields=None):
        context = {}
        exclude_fields = set(exclude_fields or [])

        for field_name, field in self._fields.items():
            if field_name in exclude_fields:
                continue

            try:
                value = getattr(self, field_name)
                if isinstance(value, models.BaseModel) and field.type == 'many2one':
                    context[f'default_{field_name}'] = value.id if value else False
                elif isinstance(value, models.Model) and field.type in ('many2many', 'one2many'):
                    context[f'default_{field_name}'] = [(6, 0, value.ids)]
                else:
                    context[f'default_{field_name}'] = value

            except Exception as e:
                _logger.warning(f"Skipped field '{field_name}' due to error: {e}")
                continue

        return context

    def get_step_id(self):
        self.ensure_one()

        if self.workflow_id == self.env.ref(self.WORKFLOW_1):
            return self.env.ref('dat_website_helpdesk.step_wf1_receiving_and_inspection').id
        elif self.workflow_id == self.env.ref(self.WORKFLOW_RETURN):
            return self.env.ref('dat_website_helpdesk.step_return_assign').id
        elif self.workflow_id == self.env.ref(self.WORKFLOW_2):
            return self.env.ref('dat_website_helpdesk.step_wf2_receiving_and_inspection').id
        elif self.workflow_id == self.env.ref(self.WORKFLOW_3):
            return self.env.ref('dat_website_helpdesk.step_wf3_receiving_and_inspection').id
        else:
            return self.env.ref('dat_website_helpdesk.step_wf4_receiving_and_inspection').id

    def clean_instance_vals(self, vals):
        for key, value in vals.items():
            if value and isinstance(value, datetime):
                dt_utc = value.astimezone(pytz.utc)
                dt_naive = dt_utc.replace(tzinfo=None)
                vals[key] = dt_naive
        return vals

    def clean_vals_list(self, vals_list):
        for vals in vals_list:
            vals = self.clean_instance_vals(vals)
        return vals_list

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = self.clean_vals_list(vals_list)
        return super().create(vals_list)
