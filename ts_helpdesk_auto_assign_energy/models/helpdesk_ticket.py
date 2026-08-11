from odoo import models, _


class HelpdeskTicket(models.Model):
    _inherit = "ticket.helpdesk"

    from odoo import models


class HelpdeskTicket(models.Model):
    _inherit = "ticket.helpdesk"

    def _ts_auto_assign_energy(self):
        """
        Hàm này được gọi sau khi tạo ticket từ wizard.
        Nhiệm vụ: gán Người xử lý = người tạo phiếu (create_uid)
        bằng cách dùng action_assigned để đi đúng quy trình.
        """
        energy_dep_ids = {
            self.env.ref("dat_website_helpdesk.dep_energy_mb").id,
            self.env.ref("dat_website_helpdesk.dep_energy_mt").id,
            self.env.ref("dat_website_helpdesk.dep_energy_mn").id,
        }

        for ticket in self:
            if not ticket.department_id or ticket.department_id.id not in energy_dep_ids:
                continue

            # người tạo phiếu (user tạo record ticket)
            user = ticket.create_uid or self.env.user
            if not user:
                continue

            # GÁN NGƯỜI XỬ LÝ ĐÚNG FLOW
            ticket.action_assigned(user)

