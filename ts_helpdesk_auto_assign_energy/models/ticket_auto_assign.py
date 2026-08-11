# -*- coding: utf-8 -*-
from ast import literal_eval
from odoo import api, models
from odoo.exceptions import ValidationError

PARAM_ENABLE = 'ts_helpdesk_auto_assign_energy.enable'
PARAM_RECEPT = 'ts_helpdesk_auto_assign_energy.auto_reception'
PARAM_DOMAIN = 'ts_helpdesk_auto_assign_energy.domain'


class TicketHelpdeskAutoAssign(models.Model):
    _inherit = 'ticket.helpdesk'   # KHÔNG sửa code cũ, chỉ kế thừa

    def _pick_user_for_ticket(self):
        """Trả về user theo mapping Chi nhánh/Bộ phận/Loại yêu cầu."""
        self.ensure_one()
        mapping = self.env['ticket.helpdesk.assignment.mapping'].sudo().search([
            ('branch_id', '=', self.branch.id),
            ('department_id', '=', self.department_id.id),
            ('ticket_type_id', '=', self.ticket_type_id.id),
        ], limit=1)
        return mapping.user_id if mapping and mapping.user_id else False

    def _auto_assign_flow(self):
        """Luồng tự động phân công khi tạo mới ticket."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()

        # 1) Kiểm tra bật/tắt
        if ICP.get_param(PARAM_ENABLE, 'False') != 'True':
            return

        # 2) Domain filter (optional)
        domain_expr = ICP.get_param(PARAM_DOMAIN, '')
        if domain_expr:
            try:
                dom = literal_eval(domain_expr)
                if not isinstance(dom, (list, tuple)):
                    raise ValueError("Domain phải là list/tuple")
            except Exception as e:
                raise ValidationError(f"Lỗi domain auto-assign: {e}")
            if not self.search_count([('id', '=', self.id)] + dom):
                return

        # 3) Nếu đã có assigned_user thì thôi
        if self.assigned_user_id:
            return

        # 4) Chọn user từ mapping
        user = self._pick_user_for_ticket()
        if not user:
            return

        ctx = dict(self.env.context, ts_auto_assign=True)

        # 5) Gọi action phân công (module cũ)
        self.with_context(ctx).sudo().action_assigned(user)

        # 6) Tự 'Tiếp nhận' nếu bật cấu hình
        if ICP.get_param(PARAM_RECEPT, 'True') == 'True':
            if hasattr(self, 'action_reception'):
                self.with_context(ctx).sudo().action_reception()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # tránh loop khi bên trong action_assigned() lại create gì đó
        if self.env.context.get('ts_auto_assign'):
            return records
        for rec in records.sudo():
            try:
                rec._auto_assign_flow()
            except Exception:
                # lỗi auto-assign không được phép chặn việc tạo ticket
                pass
        return records
