from odoo import _, models
from odoo.exceptions import UserError


class TicketHelpdesk(models.Model):
    _inherit = "ticket.helpdesk"

    def action_claim_ticket(self):
        receiving_steps = {
            "step_wf1_receiving_and_inspection",
            "step_wf2_receiving_and_inspection",
            "step_wf3_receiving_and_inspection",
            "step_wf4_receiving_and_inspection",
        }

        for ticket in self:
            if ticket.status != "new":
                raise UserError(_("Chỉ có thể tiếp nhận công việc đang chờ phân công."))

            if ticket.step_external_id not in receiving_steps:
                raise UserError(_("Công việc này không nằm ở bước chờ tiếp nhận."))

            ticket.sudo().action_assigned(self.env.user)

        return True
