from odoo import models, fields, api, _
from odoo.tools.misc import formatLang
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'abstract.custom.view']

    cancel_reason = fields.Text(string='Reason for Cancellation')
    reject_reason = fields.Text(string='Reason for Rejection')
    status = fields.Selection([
        ('draft', 'Not Sent'),
        ('waiting', 'Waiting for Approval'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string="Status", default='draft')
    customer_contact_name = fields.Char(
        string='Contact Person',
        related='ticket_id.customer_contact_name')
    formated_amount_total = fields.Char(compute='_compute_formated_amount_total')

    is_helpdesk_admin = fields.Boolean(
        string="Is Helpdesk Admin",
        compute='_compute_helpdesk_admin',
        store=False
    )
    
    @api.depends()
    def _compute_helpdesk_admin(self):
        for record in self:
            record.is_helpdesk_admin = self.env.user.has_group('dat_website_helpdesk.helpdesk_admin_lv2')

    @property
    def invisible_fields(self):
        return {
            'sale_order_template_id',
            'payment_term_id',
            'state',
            'tax_totals',
            'pricelist_id',
            'validity_date',
        }

    @property
    def invisible_form_pages(self):
        return {
            'customer_signature',
            'other_information',
            'optional_products',
        }

    @property
    def invisible_form_buttons(self):
        return {
            'action_confirm',
            'payment_action_capture',
            'payment_action_void',
        }

    def _show_cancel_wizard(self):
        """ 
        Overwrite of Odoo base.
        Decide whether the sale.order.cancel wizard should be shown to cancel specified orders.

        :return: True if there is any non-draft order in the given orders
        :rtype: bool
        """
        if self.env.context.get('disable_cancel_warning'):
            return False
        return True

    @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'order_line.price_total')
    def _compute_amounts(self):
        """
        Overwrite the Odoo base: Compute the total amounts of the SO.
        Changes: Not use tax, Combine lines with services.
        """
        super()._compute_amounts()
        for order in self:
            order.amount_tax = 0
            order.amount_total = order.amount_untaxed

    @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'order_line.price_total')
    def _compute_formated_amount_total(self):
        for rec in self:
            rec.formated_amount_total = formatLang(self.env, self.amount_total, currency_obj=rec.currency_id)

    def action_waiting_for_confirm(self):
        self.status = 'waiting'

    def action_confirm_status(self):
        self.status = 'confirmed'

    def action_open_reject_wizard(self):
        return {
            'name': 'Reject Quotation',
            'view_mode': 'form',
            'res_model': 'sale.order.reject',
            'type': 'ir.actions.act_window',
            'context': {
                'default_sale_order_id': self.id,
            },
            'target': 'new',
        }

    def action_import_products(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'quotation.product.import.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_refresh_dat_price_list(self):
        draft_orders = self.filtered(lambda order: order.status == 'draft')
        if not draft_orders:
            raise UserError(_('Chỉ có thể cập nhật đơn giá cho báo giá đang ở trạng thái nháp.'))

        updated_count, missing_count = draft_orders.mapped(
            'order_line'
        )._apply_dat_price_list()
        message = _(
            'Đã cập nhật %(updated)s dòng từ Price List.'
        ) % {'updated': updated_count}
        if missing_count:
            message += _(
                ' Có %(missing)s dòng không có mã giá phù hợp nên hệ thống giữ nguyên đơn giá hiện tại.'
            ) % {'missing': missing_count}
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cập nhật đơn giá'),
                'message': message,
                'type': 'success' if updated_count else 'warning',
                'sticky': False,
            },
        }
