import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TicketHelpDesk(models.Model):
    _inherit = 'ticket.helpdesk'

    business_unit = fields.Char(
        string='Business Unit',
        related='product_id.sap_business_unit',
        store=True,
        index=True,
        readonly=True,
    )
    number_of_warranty = fields.Integer(related='stock_lot_id.number_of_warranty', string='Number of Warranty')
    serial_warranty_supplier_id = fields.Many2one(
        'serial.warranty.supplier',
        string='Serial Warranty in Supplier')
    virtual_warehouse_entry_id = fields.Many2one(
        'virtual.warehouse.entry',
        string='Virtual Warehouse Serial Records')

    def get_assigned_user_id_based_on_department(self, department=None, branch=None, ticket_type=None,
                                                 stock_lot=None):
        if not department:
            raise ValidationError(_("Hiện tại chưa có bộ phận phụ trách loại yêu cầu này!"))

        mapping_env = self.env['ticket.helpdesk.assignment.mapping'].sudo()
        special_type_ids = mapping_env._get_special_type_ids()

        # Trường hợp có lot và type thuộc nhóm special: tìm theo BU
        if stock_lot and ticket_type and ticket_type.id in special_type_ids:
            bu = stock_lot.product_id.business_unit_id
            if bu:
                mapping = mapping_env.search([
                    ('branch_id', '=', branch.id),
                    ('department_id', '=', department.id),
                    ('ticket_type_id', '=', ticket_type.id),
                    ('business_unit_ids', 'in', bu.id),
                ], limit=1)
                if mapping and mapping.user_id:
                    return mapping.user_id

        # Fallback: tìm mapping chỉ theo Branch/Department/Type
        if branch and ticket_type:
            mapping = mapping_env.search([
                ('branch_id', '=', branch.id),
                ('department_id', '=', department.id),
                ('ticket_type_id', '=', ticket_type.id),
            ], limit=1)
            if mapping and mapping.user_id:
                return mapping.user_id

        # Nếu vẫn không có mapping, trả về manager của department
        manager = department.sudo().manager_id
        if manager and manager.user_id:
            return manager.user_id

        return False

    def action_next_step_wf1_step5_repair(self):
        res = super().action_next_step_wf1_step5_repair()

        if self.warranty_service_type == 'repair':
            self.update_product_repair_info()
        elif self.warranty_service_type == 'replace':
            self.update_replacement_product_info()

        return res

    def update_product_repair_info(self):
        self.env['serial.health.history'].create({
            'status_before_repair': self.status_before_repair,
            'status_after_repair': self.status_after_repair,
            'lot_id': self.stock_lot_id.id,
            'recorded_by': self.assigned_user_id.id,
        })

    def update_replacement_product_info(self):
        self.ensure_one()
        serial_number = (self.replace_serial_number or '').strip()
        if not serial_number:
            raise ValidationError(_('The replacement serial number is required!'))

        old_lot = self.stock_lot_id.sudo()
        new_lot = self.env['stock.lot'].sudo().search(
            [('name', '=', serial_number)], limit=1
        )
        lot_values = {
            'name': serial_number,
            'product_id': old_lot.product_id.id,
            'product_qty': old_lot.product_qty,
            'buyer_id': (self.customer_id or self.owner_id).id,
            'owner_id': (self.owner_id or self.customer_id).id,
            'company_id': old_lot.company_id.id,
            # Continue the original warranty instead of starting a new term.
            'warranty_start_date': old_lot.warranty_start_date,
            'warranty_month': old_lot.warranty_month,
        }
        if new_lot:
            lot_values.pop('name')
            new_lot.write(lot_values)
        else:
            new_lot = self.env['stock.lot'].sudo().create(lot_values)

        old_lot.write({'replaced_by': new_lot.id})
        if 'new_stock_lot_id' in self._fields:
            self.new_stock_lot_id = new_lot

    def action_create_serial_warranty_in_supplier(self):
        noti_type = 'danger'
        serial_number = self.stock_lot_id.name or ''
        noti_message = _(
            'Failed to create the new warranty in the supplier system for serial number %s.'
        ) % serial_number
        try:
            new_rec = self.env['serial.warranty.supplier'].create({
                'ticket_id': self.id,
                'lot_id': self.stock_lot_id.id,
                'company_id': self.env.user.company_id.id,
            })
            if new_rec:
                self.serial_warranty_supplier_id = new_rec.id
                noti_type = 'success'
                noti_message = _(
                    'Successfully created a new warranty in the supplier system for serial number %s.'
                ) % serial_number
                self._message_log_batch(bodies={self.id: noti_message})
        except Exception:
            pass
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': noti_type,
                'sticky': False,
                'message': noti_message,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }

    def action_create_virtual_warehouse_entry(self):
        noti_type = 'danger'
        serial_number = self.stock_lot_id.name or ''
        noti_message = _(
            'Failed to create the new Virtual Warehouse entry for serial number %s.'
        ) % serial_number
        try:
            new_entry = self.env['virtual.warehouse.entry'].create({
                'ticket_id': self.id,
                'lot_id': self.stock_lot_id.id,
                'company_id': self.branch.id,
            })
            if new_entry:
                self.virtual_warehouse_entry_id = new_entry.id
                noti_type = 'success'
                noti_message = _(
                    'Successfully created a new Virtual Warehouse entry for serial number %s.'
                ) % serial_number
                self._message_log_batch(bodies={self.id: noti_message})
        except Exception:
            pass
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': noti_type,
                'sticky': False,
                'message': noti_message,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_open_serial_warranty_in_supplier(self):
        self.ensure_one()
        if self.serial_warranty_supplier_id:
            return {
                'name': 'Serial Warranty Supplier',
                'res_model': 'serial.warranty.supplier',
                'view_id': False,
                'res_id': self.serial_warranty_supplier_id.id,
                'view_mode': 'form',
                'type': 'ir.actions.act_window',
            }

    def action_open_virtual_warehouse_entry(self):
        self.ensure_one()
        if self.virtual_warehouse_entry_id:
            return {
                'name': 'Virtual Warehouse Serial Records',
                'res_model': 'virtual.warehouse.entry',
                'view_id': False,
                'res_id': self.virtual_warehouse_entry_id.id,
                'view_mode': 'form',
                'type': 'ir.actions.act_window',
            }

    def action_reception(self):
        super().action_reception()
        if self.workflow_id == self.env.ref('dat_website_helpdesk.workflow_1'):
            self.action_create_virtual_warehouse_entry()

    def action_next_step_wf1_step2_receiving(self):
        super().action_next_step_wf1_step2_receiving()

        ticket_type_1 = self.env.ref('dat_website_helpdesk.ticket_type_1')
        ticket_type_2 = self.env.ref('dat_website_helpdesk.ticket_type_2')
        ticket_type_3 = self.env.ref('dat_website_helpdesk.ticket_type_3')

        is_warranty = self.product_warranty_status == 'warranty'
        requires_materials = self.require_materials == 'yes'
        is_valid_ticket_type = self.ticket_type_id in (ticket_type_1, ticket_type_2, ticket_type_3)

        if is_warranty and requires_materials and is_valid_ticket_type:
            self.action_create_serial_warranty_in_supplier()
