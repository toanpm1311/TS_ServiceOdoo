# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HelpdeskAutoAssignRule(models.Model):
    _name = "ts.helpdesk.auto.assign.rule"
    _description = "Helpdesk Auto Assign Rule (Energy)"
    _order = "sequence asc, id asc"

    name = fields.Char("Tên rule", required=True)
    active = fields.Boolean("Kích hoạt", default=True)
    sequence = fields.Integer("Thứ tự", default=10)

    # CHÚ Ý: tùy hệ thống anh, nếu team model là khác thì đổi lại
    # Nếu anh vẫn dùng helpdesk.team chuẩn thì giữ nguyên
    team_id = fields.Many2one(
        "helpdesk.team",
        string="Nhóm hỗ trợ",
        required=True,
        help="Rule chỉ áp dụng cho team này.",
    )

    user_id = fields.Many2one(
        "res.users",
        string="Người xử lý",
        help="Ticket sẽ được phân công cho user này.",
    )

    stage_id = fields.Many2one(
        "helpdesk.stage",
        string="Bước",
        help="Đổi ticket sang bước này khi áp dụng rule.",
    )

    priority = fields.Selection(
        [
            ("0", "Thấp"),
            ("1", "Bình thường"),
            ("2", "Cao"),
            ("3", "Rất cao"),
        ],
        string="Mức độ ưu tiên",
        help="Nếu chọn, rule chỉ áp dụng cho ticket có mức ưu tiên tương ứng.",
    )

    activity_type_id = fields.Many2one(
        "mail.activity.type",
        string="Loại hoạt động",
        help="Tạo activity với loại này (nếu chọn).",
    )
    activity_user_id = fields.Many2one(
        "res.users",
        string="Người được giao activity",
        help="User nhận activity nhắc việc (nếu chọn).",
    )

    domain = fields.Text(
        "Domain bổ sung trên ticket",
        help=(
            "Domain Odoo (Python) áp dụng trên ticket.helpdesk.\n"
            "Ví dụ: [('x_region', '=', 'HCM'), ('priority', 'in', ['2', '3'])]"
        ),
    )
