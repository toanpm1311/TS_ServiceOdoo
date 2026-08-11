from odoo import models


class CreateTicketWizard(models.TransientModel):
    _inherit = "create.ticket.wizard"

    def _action_create(self):
        """
        Gọi logic gốc của DAT để tạo ticket,
        sau đó cho module auto-assign của mình xử lý gán người.
        """
        tickets = super()._action_create()

        # kiểm tra cấu hình bật/tắt auto-assign
        param = self.env["ir.config_parameter"].sudo().get_param(
            "ts_helpdesk_auto_assign_energy.auto_assign_enabled", "False"
        )
        if str(param).lower() not in ("true", "1", "yes"):
            return tickets

        # Gọi hàm auto-assign của module mình
        tickets._ts_auto_assign_energy()

        return tickets
