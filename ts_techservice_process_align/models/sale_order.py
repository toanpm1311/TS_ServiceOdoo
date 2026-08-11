from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    ts_pair_role = fields.Selection(selection_add=[("return", "SO trả hàng")], ondelete={"return": "set default"})

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            if order.ticket_id and getattr(order, "ts_pair_role", False) == "return":
                order.ticket_id.write({
                    "ts_return_so_required": True,
                    "is_need_new_so": False,
                })
                if hasattr(order.ticket_id, "_ts_create_audit_log"):
                    order.ticket_id._ts_create_audit_log(
                        name="Đã tạo SO trả hàng",
                        change_scope="order",
                        change_type="create",
                        field_name="sale_order_ids",
                        new_value=order.name,
                        reason="SO trả hàng được tạo từ nhánh trả khách.",
                    )
        return orders
