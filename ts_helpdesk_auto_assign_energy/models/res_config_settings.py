from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ts_auto_assign_enable = fields.Boolean(
        string="Kích hoạt tự động phân công Helpdesk (Energy)",
        config_parameter="ts_helpdesk_auto_assign_energy.auto_assign_enabled",
        help="Nếu bật, ticket helpdesk mảng Năng lượng sẽ tự động phân công theo các rule Auto-Assign (Energy).",
    )
