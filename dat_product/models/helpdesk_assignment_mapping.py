# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

class HelpdeskAssignmentMapping(models.Model):
    _inherit = 'ticket.helpdesk.assignment.mapping'

    SPECIAL_TICKET_TYPE_XMLIDS = (
        'dat_website_helpdesk.ticket_type_1',
        'dat_website_helpdesk.ticket_type_2',
        'dat_website_helpdesk.ticket_type_3',
    )

    business_unit_ids = fields.Many2many(
        'product.business.unit',
        'ticket_assignment_bu_rel',
        'mapping_id',
        'business_unit_id',
        string='Business Units'
    )
    ticket_type_external_id = fields.Char(
        string='Ticket Type XML ID',
        compute='_compute_ticket_type_external_id',
        store=True,
        readonly=True,
    )

    def init(self):
        super(HelpdeskAssignmentMapping, self).init()
        tools.drop_constraint(self.env.cr, 'ticket_helpdesk_assignment_mapping', 'ticket_helpdesk_assignment_mapping_unique_branch_dept_type')

    @api.model
    def _get_special_type_ids(self):
        """Trả về list các res_id của ticket_type đặc biệt."""
        return [
            self.env.ref(xmlid).id
            for xmlid in self.SPECIAL_TICKET_TYPE_XMLIDS
        ]

    @api.depends('ticket_type_id')
    def _compute_ticket_type_external_id(self):
        for rec in self:
            external_ids = rec.ticket_type_id._get_external_ids()
            ext = [
                x.split('.', 1)[1]
                for x in external_ids.get(rec.ticket_type_id.id, [])
                if x.split('.', 1)[0] == 'dat_website_helpdesk'
            ]
            rec.ticket_type_external_id = ext[0] if ext else False

    @api.onchange('ticket_type_id')
    def _onchange_ticket_type_id(self):
        """Nếu đổi type và không thuộc nhóm special thì clear BU."""
        special_ids = self._get_special_type_ids()
        if self.ticket_type_id and self.ticket_type_id.id not in special_ids:
            # Reset tất cả business_unit_ids
            self.business_unit_ids = [(5, 0, 0)]

    @api.constrains('ticket_type_id', 'business_unit_ids')
    def _check_business_unit_required(self):
        """Chỉ bắt buộc BU khi type nằm trong special."""
        special_ids = self._get_special_type_ids()
        for rec in self:
            if rec.ticket_type_id.id in special_ids and not rec.business_unit_ids:
                raise ValidationError(_(
                    "Với Loại yêu cầu '%s', bạn phải chọn ít nhất một Mảng kinh doanh."
                ) % rec.ticket_type_id.name)

    @api.constrains('branch_id', 'department_id', 'ticket_type_id', 'business_unit_ids')
    def _check_unique_mapping(self):
        """
        - Với type thường: duy nhất (branch, dept, type)
        - Với type special: không overlap BU
        """
        special_ids = self._get_special_type_ids()
        for rec in self:
            base = [
                ('branch_id', '=', rec.branch_id.id),
                ('department_id', '=', rec.department_id.id),
                ('ticket_type_id', '=', rec.ticket_type_id.id),
                ('id', '!=', rec.id),
            ]
            if rec.ticket_type_id.id in special_ids:
                for bu in rec.business_unit_ids:
                    if self.search(base + [('business_unit_ids', 'in', bu.id)], limit=1):
                        raise ValidationError(_(
                            "Mapping cho Khu vực '%s', Lĩnh vực '%s', Loại yêu cầu '%s' "
                            "và Mảng kinh doanh '%s' đã tồn tại."
                        ) % (
                            rec.branch_id.name,
                            rec.department_id.name,
                            rec.ticket_type_id.name,
                            bu.code or bu.name,
                        ))
            else:
                if self.search(base, limit=1):
                    raise ValidationError(_(
                        "Mapping cho Khu vực '%s', Lĩnh vực '%s' và Loại yêu cầu '%s' đã tồn tại."
                    ) % (
                        rec.branch_id.name,
                        rec.department_id.name,
                        rec.ticket_type_id.name,
                    ))
