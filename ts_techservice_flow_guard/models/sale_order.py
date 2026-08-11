from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    ts_allow_post_so_price_edit = fields.Boolean(
        string='Cho phép sửa báo giá sau SO',
        default=True,
        help='Nếu bỏ chọn, hệ thống sẽ chặn sửa giá / vật tư sau khi SO hoặc ĐXVT đã xác nhận, trừ khi truyền context ts_allow_post_so_edit=True.'
    )
    ts_master_code = fields.Char(string='Mã Techservice chính', related='ticket_id.ts_master_code', store=True, readonly=True)
    ts_audit_log_ids = fields.One2many('ts.techservice.audit.log', 'order_id', string='Nhật ký kiểm soát', readonly=True)
    ts_audit_log_count = fields.Integer(string='Số nhật ký kiểm soát', compute='_compute_ts_audit_log_count')
    ts_customer_progress = fields.Char(string='Tiến độ khách hàng', related='ticket_id.ts_customer_progress', store=True, readonly=True)
    ts_price_impact_review_required = fields.Boolean(string='Cần rà soát ảnh hưởng giá', readonly=True, copy=False)
    ts_last_price_change_at = fields.Datetime(string='Lần đổi giá gần nhất', readonly=True, copy=False)
    ts_last_price_change_note = fields.Char(string='Ghi chú đổi giá gần nhất', readonly=True, copy=False)
    ts_pair_role = fields.Selection([
        ('primary', 'SO chính'),
        ('secondary', 'SO phụ'),
    ], string='Vai trò cặp SO', default='primary', copy=False)
    ts_pair_origin_order_id = fields.Many2one('sale.order', string='SO gốc của cặp', copy=False, readonly=True)
    ts_pair_order_ids = fields.One2many('sale.order', 'ts_pair_origin_order_id', string='Các SO ghép cặp', readonly=True)
    ts_paired_so_count = fields.Integer(string='Số SO ghép cặp', compute='_compute_ts_paired_so_count')
    ts_merged_into_order_id = fields.Many2one(
        'sale.order',
        string='Đã gộp vào báo giá',
        copy=False,
        readonly=True,
        index=True,
    )
    ts_merged_source_order_ids = fields.One2many(
        'sale.order',
        'ts_merged_into_order_id',
        string='Báo giá nguồn đã gộp',
        readonly=True,
    )
    ts_quotation_ticket_ids = fields.Many2many(
        'ticket.helpdesk',
        'ts_sale_order_ticket_rel',
        'order_id',
        'ticket_id',
        string='Các ticket trên báo giá tổng',
        copy=False,
        readonly=True,
    )
    ts_merge_customer_id = fields.Many2one(
        'res.partner',
        string='Khách hàng gộp báo giá',
        compute='_compute_ts_merge_customer_id',
        store=True,
        readonly=True,
        index=True,
    )
    ts_bound_stage = fields.Selection([
        ('normal', 'Thông thường'),
        ('intermediate', 'Gắn từ kho trung gian'),
    ], string='Mốc gắn đơn', default='normal', copy=False)

    def _compute_ts_audit_log_count(self):
        for rec in self:
            rec.ts_audit_log_count = len(rec.ts_audit_log_ids)

    def _compute_ts_paired_so_count(self):
        for rec in self:
            rec.ts_paired_so_count = len(rec.ts_pair_order_ids)

    @api.depends(
        'ticket_owner_id.commercial_partner_id',
        'partner_id.commercial_partner_id',
    )
    def _compute_ts_merge_customer_id(self):
        for order in self:
            customer = order.ticket_owner_id or order.partner_id
            order.ts_merge_customer_id = customer.commercial_partner_id

    def _ts_is_edit_locked(self):
        self.ensure_one()
        return bool(
            getattr(self, 'sap_status', False)
            or (self.ticket_id and (getattr(self.ticket_id, 'sap_sale_order_number', False) or getattr(self.ticket_id, 'sap_dxvt_order_number', False)))
            or getattr(self, 'status', False) in ('confirmed', 'rejected', 'cancelled')
            or self.state in ('sale', 'done', 'cancel')
        )

    def _ts_create_audit_log(self, **vals):
        self.env['ts.techservice.audit.log'].sudo().create({
            'name': vals.get('name') or _('Nhật ký kiểm soát báo giá'),
            'order_id': self.id,
            'ticket_id': self.ticket_id.id,
            'line_id': vals.get('line_id'),
            'change_scope': vals.get('change_scope', 'order'),
            'change_type': vals.get('change_type', 'update'),
            'field_name': vals.get('field_name'),
            'old_value': vals.get('old_value'),
            'new_value': vals.get('new_value'),
            'reason': vals.get('reason'),
        })

    @staticmethod
    def _ts_to_text(value):
        if value is False or value is None:
            return False
        if hasattr(value, 'display_name'):
            return value.display_name
        return str(value)

    @classmethod
    def _ts_tracked_order_fields(cls):
        return ['status', 'warehouse_id', 'filler_warehouse_id', 'address2', 'document_note', 'note', 'partner_id']

    @classmethod
    def _ts_guarded_header_fields(cls):
        return ['warehouse_id', 'filler_warehouse_id', 'address2', 'document_note', 'note']

    @classmethod
    def _ts_edited_header_fields(cls, vals):
        tracked = set(cls._ts_tracked_order_fields())
        return sorted(tracked.intersection(set(vals.keys())))

    @classmethod
    def _ts_allow_context_edit(cls, env):
        return bool(env.context.get('ts_allow_post_so_edit'))

    @classmethod
    def _ts_should_notify_new_quote(cls, env, vals):
        return bool(vals.get('ticket_id') and env.context.get('from_ticket_helpdesk'))

    def _ts_guard_post_so_header_edit(self, vals):
        guarded_fields = set(self._ts_guarded_header_fields()).intersection(set(vals.keys()))
        if not guarded_fields or self._ts_allow_context_edit(self.env):
            return
        for order in self:
            if order._ts_is_edit_locked() and not order.ts_allow_post_so_price_edit:
                raise UserError(_(
                    'Báo giá / SO này đã ở giai đoạn sau SO. Hệ thống khóa sửa các trường: %s. '
                    'Hãy bật "Cho phép sửa báo giá sau SO" hoặc truyền context ts_allow_post_so_edit=True nếu chủ động cho phép.'
                ) % ', '.join(sorted(guarded_fields)))

    def _ts_mark_price_impact(self, note):
        self.write({
            'ts_price_impact_review_required': True,
            'ts_last_price_change_at': fields.Datetime.now(),
            'ts_last_price_change_note': note,
        })
        if self.ticket_id and hasattr(self.ticket_id, '_ts_notify_internal_event'):
            self.ticket_id._ts_notify_internal_event(
                title=_('Cần rà soát ảnh hưởng khi đổi giá'),
                body=_('Đơn %(order)s vừa có thay đổi giá / vật tư: %(note)s') % {'order': self.name, 'note': note},
            )

    def action_ts_bind_from_intermediate(self):
        for order in self:
            order.write({'ts_bound_stage': 'intermediate'})
            if order.ticket_id:
                order.ticket_id.write({'ts_bind_from_intermediate': True})
            order._ts_create_audit_log(
                name=_('Đơn được gắn từ mốc kho trung gian'),
                change_scope='workflow',
                change_type='update',
                field_name='ts_bound_stage',
                new_value='intermediate',
            )
        return True

    def action_ts_create_paired_so(self):
        self.ensure_one()
        existing_pair = self.ts_pair_order_ids[:1]
        if existing_pair:
            return existing_pair

        copy_vals = {
            'ts_pair_origin_order_id': self.id,
            'ts_pair_role': 'secondary',
            'client_order_ref': _('%s - phụ') % (self.name or ''),
            'origin': self.name,
        }
        if self.ticket_id and self.ticket_id.ts_target_warehouse_id and 'warehouse_id' in self._fields:
            copy_vals['warehouse_id'] = self.ticket_id.ts_target_warehouse_id.id
        if self.ticket_id and self.ticket_id.ts_intermediate_warehouse_id and 'filler_warehouse_id' in self._fields:
            copy_vals['filler_warehouse_id'] = self.ticket_id.ts_intermediate_warehouse_id.id

        pair = self.copy(copy_vals)
        self._ts_create_audit_log(
            name=_('Đã tạo SO phụ'),
            change_scope='order',
            change_type='create',
            field_name='ts_pair_order_ids',
            new_value=pair.name,
            reason=_('Tạo để phục vụ luồng SO hai nhánh.'),
        )
        if self.ticket_id and hasattr(self.ticket_id, '_ts_notify_internal_event'):
            self.ticket_id._ts_notify_internal_event(
                title=_('Đã tạo SO phụ'),
                body=_('SO chính %(primary)s đã tạo SO phụ %(secondary)s.') % {
                    'primary': self.name,
                    'secondary': pair.name,
                },
            )
        return pair

    def action_ts_open_merge_wizard(self):
        orders = self.exists()
        if not orders:
            raise UserError(_('Vui lòng chọn báo giá cần gộp.'))
        return {
            'name': _('Gộp báo giá Techservice'),
            'type': 'ir.actions.act_window',
            'res_model': 'ts.sale.order.merge.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'sale.order',
                'active_id': orders[:1].id,
                'active_ids': orders.ids,
                'default_base_order_id': orders[:1].id,
                'default_merge_order_ids': [fields.Command.set(orders[1:].ids)],
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order, vals in zip(orders, vals_list):
            if order.ticket_id:
                order.ticket_id._ts_ensure_master_code()
                if not order.ts_quotation_ticket_ids:
                    order.with_context(ts_skip_merge_sync=True).write({
                        'ts_quotation_ticket_ids': [fields.Command.link(order.ticket_id.id)],
                    })
            order._ts_create_audit_log(
                name=_('Đã tạo báo giá / SO'),
                change_scope='order',
                change_type='create',
                new_value=order.name,
                reason=_('Tạo từ luồng Techservice') if self._ts_should_notify_new_quote(self.env, vals) else False,
            )
            if self._ts_should_notify_new_quote(self.env, vals) and order.ticket_id:
                order.ticket_id._ts_notify_new_quotation(order)
        return orders

    def write(self, vals):
        self._ts_guard_post_so_header_edit(vals)
        tracked_fields = self._ts_edited_header_fields(vals)
        snapshot = {
            order.id: {field: order[field] for field in tracked_fields}
            for order in self
        }
        before_status = {order.id: (getattr(order, 'status', False), order.state) for order in self}
        res = super().write(vals)
        for order in self:
            for field in tracked_fields:
                old = snapshot[order.id].get(field)
                new = order[field]
                if self._ts_to_text(old) == self._ts_to_text(new):
                    continue
                order._ts_create_audit_log(
                    name=_('Đã cập nhật báo giá / SO'),
                    change_scope='order',
                    change_type='update' if field != 'status' else 'status',
                    field_name=field,
                    old_value=self._ts_to_text(old),
                    new_value=self._ts_to_text(new),
                )
            old_status, old_state = before_status.get(order.id, (False, False))
            if old_status != getattr(order, 'status', False) or old_state != order.state:
                if order.ticket_id and hasattr(order.ticket_id, '_ts_notify_internal_event'):
                    order.ticket_id._ts_notify_internal_event(
                        title=_('SO thay đổi trạng thái'),
                        body=_('Đơn %(order)s đổi trạng thái từ %(old)s/%(old_state)s sang %(new)s/%(new_state)s.') % {
                            'order': order.name,
                            'old': old_status or '-',
                            'old_state': old_state or '-',
                            'new': getattr(order, 'status', False) or '-',
                            'new_state': order.state or '-',
                        },
                    )
        if not self.env.context.get('ts_skip_merge_sync'):
            sync_fields = {
                field_name: vals[field_name]
                for field_name in (
                    'status',
                    'reject_reason',
                    'cancel_reason',
                    'sap_status',
                )
                if field_name in vals
            }
            if sync_fields:
                merged_sources = self.mapped('ts_merged_source_order_ids')
                if merged_sources:
                    merged_sources.with_context(
                        ts_allow_post_so_edit=True,
                        ts_skip_merge_sync=True,
                    ).write(sync_fields)
        return res
