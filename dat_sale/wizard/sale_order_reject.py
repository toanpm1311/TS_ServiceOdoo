from odoo import _, fields, models


class SaleOrderReject(models.TransientModel):
    _name = "sale.order.reject"
    _description = "Sale Order Reject"

    sale_order_id = fields.Many2one('sale.order', string='Quotation', required=True)
    reject_reason = fields.Text(string='Reason for Rejection', required=True)

    def action_reject(self):
        self.sale_order_id.sudo().write({
            'status': 'rejected',
            'reject_reason': self.reject_reason,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'sticky': False,
                'message': _('Quotation has been rejected.'),
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
