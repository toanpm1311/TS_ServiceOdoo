from odoo import fields, models


class SaleOrderCancel(models.TransientModel):
    _name = 'sale.order.cancel'
    _inherit = ['sale.order.cancel', 'abstract.custom.view']

    order_id = fields.Many2one('sale.order', string='Sale Order', required=True)
    cancel_reason = fields.Text(string='Reason for Cancellation')

    @property
    def invisible_fields(self):
        return self._fields.keys() - {'order_id', 'cancel_reason'}

    @property
    def invisible_form_buttons(self):
        return {
            'action_send_mail_and_cancel'
        }

    def action_cancel(self):
        res = super().action_cancel()
        if res:
            self.order_id.cancel_reason = self.cancel_reason
            self.order_id.status = 'cancelled'
        return res
