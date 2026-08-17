from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TicketHelpDesk(models.Model):
    _inherit = 'ticket.helpdesk'

    ts_master_code = fields.Char(string='Mã Techservice chính', copy=False, readonly=True, index=True)
    ts_material_proposal_status = fields.Selection([
        ('draft', 'Nháp'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Từ chối'),
    ], string='Trạng thái đề xuất vật tư', compute='_compute_ts_material_proposal_status', store=True)
    ts_customer_progress = fields.Char(string='Tiến độ khách hàng', compute='_compute_ts_customer_progress', store=True)
    ts_source_warehouse_id = fields.Many2one('stock.warehouse', string='Kho nguồn')
    ts_intermediate_warehouse_id = fields.Many2one('stock.warehouse', string='Kho trung gian')
    ts_target_warehouse_id = fields.Many2one('stock.warehouse', string='Kho đích')
    ts_bind_from_intermediate = fields.Boolean(string='Gắn từ kho trung gian', default=False)
    ts_quote_zns_sent = fields.Boolean(string='Đã gửi ZNS báo giá', readonly=True)
    ts_quote_zns_sent_at = fields.Datetime(string='Thời điểm gửi ZNS báo giá', readonly=True)
    ts_last_serial_sync_at = fields.Datetime(string='Lần cập nhật serial gần nhất', readonly=True)
    ts_last_serial_sync_note = fields.Char(string='Ghi chú cập nhật serial gần nhất', readonly=True)
    ts_serial_synced = fields.Boolean(string='Đã đồng bộ serial', readonly=True)
    ts_last_rule_check_at = fields.Datetime(string='Lần kiểm tra rule gần nhất', readonly=True)
    ts_rule_check_note = fields.Text(string='Kết quả kiểm tra rule', readonly=True)
    ts_consolidated_order_ids = fields.Many2many(
        'sale.order',
        'ts_sale_order_ticket_rel',
        'ticket_id',
        'order_id',
        string='Báo giá tổng',
        readonly=True,
    )

    def _ts_get_effective_sale_orders(self):
        self.ensure_one()
        own_orders = self.sale_order_ids.filtered(
            lambda order: not order.ts_merged_into_order_id
        )
        return own_orders | self.ts_consolidated_order_ids.filtered(
            lambda order: not order.ts_merged_into_order_id
        )

    def action_open_quotation(self):
        self.ensure_one()
        orders = self._ts_get_effective_sale_orders()
        if not orders:
            return super().action_open_quotation()
        if len(orders) == 1:
            return {
                'name': _('Báo giá'),
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': orders.id,
                'view_mode': 'form',
            }
        return {
            'name': _('Báo giá'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'domain': [('id', 'in', orders.ids)],
            'view_mode': 'tree,form',
        }

    def _ts_ensure_master_code(self):
        seq = self.env['ir.sequence']
        for rec in self:
            if not rec.ts_master_code:
                rec.ts_master_code = seq.next_by_code('ts.techservice.master.code') or '/'
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('ts_master_code'):
                vals['ts_master_code'] = self.env['ir.sequence'].next_by_code('ts.techservice.master.code') or '/'
        return super().create(vals_list)

    @api.depends(
        'sale_order_feedback',
        'sale_order_ids.status',
        'sale_order_ids.state',
        'ts_consolidated_order_ids.status',
        'ts_consolidated_order_ids.state',
    )
    def _compute_ts_material_proposal_status(self):
        for rec in self:
            orders = rec._ts_get_effective_sale_orders()
            statuses = set(orders.mapped('status'))
            states = set(orders.mapped('state'))
            if 'confirmed' in statuses or states.intersection({'sale', 'done'}):
                rec.ts_material_proposal_status = 'approved'
            elif statuses and statuses.issubset({'rejected', 'cancelled'}):
                rec.ts_material_proposal_status = 'rejected'
            elif rec.sale_order_feedback == 'refuse':
                rec.ts_material_proposal_status = 'rejected'
            else:
                rec.ts_material_proposal_status = 'draft'

    @api.depends(
        'status',
        'step_id',
        'sap_sale_order_number',
        'sap_dxvt_order_number',
        'sale_order_ids.status',
        'sale_order_ids.state',
        'ts_consolidated_order_ids.status',
        'ts_consolidated_order_ids.state',
    )
    def _compute_ts_customer_progress(self):
        for rec in self:
            orders = rec._ts_get_effective_sale_orders()
            progress = _('Mới')
            confirmed_so = orders.filtered(
                lambda so: getattr(so, 'status', False) == 'confirmed' or so.state in ('sale', 'done')
            )
            if rec.status == 'closed':
                progress = _('Hoàn thành')
            elif rec.status == 'rejected':
                progress = _('Trả lại / từ chối')
            elif getattr(rec, 'sap_dxvt_order_number', False):
                progress = _('Đang xử lý kho / đã tạo ĐXVT')
            elif getattr(rec, 'sap_sale_order_number', False) or confirmed_so:
                progress = _('Đã tạo SO / chờ thực hiện')
            elif orders:
                progress = _('Đã tạo báo giá / chờ khách phản hồi')
            elif rec.step_id:
                progress = rec.step_id.name
            rec.ts_customer_progress = progress

    def _ts_create_audit_log(self, **vals):
        self.env['ts.techservice.audit.log'].sudo().create({
            'ticket_id': self.id,
            'name': vals.get('name') or _('Nhật ký kiểm soát ticket'),
            'change_scope': vals.get('change_scope', 'workflow'),
            'change_type': vals.get('change_type', 'update'),
            'field_name': vals.get('field_name'),
            'old_value': vals.get('old_value'),
            'new_value': vals.get('new_value'),
            'reason': vals.get('reason'),
        })

    def _ts_notify_internal_event(self, title, body):
        self.ensure_one()
        partner_ids = []
        if getattr(self, 'assigned_user_id', False) and self.assigned_user_id.partner_id:
            partner_ids.append(self.assigned_user_id.partner_id.id)
        if getattr(self, 'assigned_follower_ids', False):
            partner_ids += self.assigned_follower_ids.mapped('partner_id').ids
        partner_ids = list(set([pid for pid in partner_ids if pid]))
        full_body = '<b>%s</b><br/>%s' % (title, body)
        self.message_post(body=full_body, partner_ids=partner_ids or None)
        self._ts_create_audit_log(
            name=title,
            change_scope='notification',
            change_type='notify',
            field_name='internal_notification',
            reason=body,
        )

    def action_ts_run_rule_check(self):
        for rec in self:
            issues = []
            if not getattr(rec, 'customer_id', False):
                issues.append(_('Thiếu khách hàng.'))
            if not getattr(rec, 'step_id', False):
                issues.append(_('Thiếu bước hiện tại.'))
            if rec.sale_order_feedback == 'refuse' and getattr(rec, 'sap_dxvt_order_number', False):
                issues.append(_('Đã có ĐXVT dù báo giá / đề xuất vật tư bị từ chối.'))
            if rec.ts_bind_from_intermediate and not rec.ts_intermediate_warehouse_id:
                issues.append(_('Đã bật gắn từ kho trung gian nhưng chưa chọn kho trung gian.'))
            if rec.sale_order_ids and not rec.ts_master_code:
                rec._ts_ensure_master_code()
            if rec.sale_order_ids and not rec.ts_master_code:
                issues.append(_('Chưa có mã Techservice chính dù đã có báo giá / SO.'))
            note = '\n'.join(issues) if issues else _('Không phát hiện lỗi chặn nào theo rule kiểm tra của addon.')
            rec.write({
                'ts_last_rule_check_at': fields.Datetime.now(),
                'ts_rule_check_note': note,
            })
            rec._ts_create_audit_log(
                name=_('Đã chạy kiểm tra rule'),
                change_scope='workflow',
                change_type='update',
                field_name='ts_rule_check_note',
                new_value=note,
            )
        return True

    def action_next_step_wf1_step4_material_dispatch(self):
        self.ensure_one()
        if self.sale_order_feedback == 'refuse' or self.ts_material_proposal_status == 'rejected':
            prev_step = self.step_id.name or ''
            if 'reassembly' in self._fields:
                self.reassembly = True
            return_step = False
            if hasattr(self, 'WORKFLOW_1_STEP_6'):
                return_step = self.env.ref(self.WORKFLOW_1_STEP_6, raise_if_not_found=False)
            if return_step:
                self.step_id = return_step
            body = _(
                'ĐXVT đã bị chặn vì đề xuất vật tư / phản hồi báo giá bị từ chối. '
                'Phiếu được chuyển về nhánh trả khách / hoàn trạng.'
            )
            if hasattr(self, '_message_log_batch'):
                self._message_log_batch(bodies={self.id: body})
            else:
                self.message_post(body=body)
            self._ts_notify_internal_event(_('Đã chặn ĐXVT'), body)
            self._ts_create_audit_log(
                name=_('Chặn ĐXVT do báo giá / đề xuất vật tư bị từ chối'),
                change_scope='workflow',
                change_type='guard',
                field_name='step_id',
                old_value=prev_step,
                new_value=self.step_id.name if self.step_id else False,
                reason=body,
            )
            return True

        if getattr(self, 'sap_dxvt_order_number', False):
            return super().action_next_step_wf1_step4_material_dispatch()

        confirmed_so = self._ts_get_effective_sale_orders().filtered(
            lambda so: getattr(so, 'status', False) == 'confirmed'
            or so.state in ('sale', 'done')
        )[:1]
        if not confirmed_so:
            raise ValidationError(_('Chỉ được qua bước ĐXVT khi đã có báo giá / SO được xác nhận.'))

        return super().action_next_step_wf1_step4_material_dispatch()

    def _ts_notify_new_quotation(self, order):
        self.ensure_one()
        body = _(
            'Đã tạo báo giá mới cho phiếu %(ticket)s: <b>%(order)s</b>. '
            'Tổng tiền: %(amount)s.'
        ) % {
            'ticket': self.display_name,
            'order': order.name or _('Mới'),
            'amount': order.amount_total,
        }
        self._ts_notify_internal_event(_('Đã tạo báo giá mới'), body)
        self._ts_send_quotation_zns(order)

    def _ts_send_quotation_zns(self, order):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        xmlid = (ICP.get_param('ts_techservice_flow_guard.zns_template_xmlid') or '').strip()
        if not xmlid:
            self._ts_create_audit_log(
                name=_('Bỏ qua gửi ZNS báo giá'),
                change_scope='notification',
                change_type='notify',
                field_name='zns',
                reason=_('Chưa cấu hình XMLID mẫu ZNS trong ts_techservice_flow_guard.zns_template_xmlid'),
            )
            return False

        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            self._ts_create_audit_log(
                name=_('Bỏ qua gửi ZNS báo giá'),
                change_scope='notification',
                change_type='notify',
                field_name='zns',
                reason=_('Không tìm thấy XMLID mẫu ZNS đã cấu hình: %s') % xmlid,
            )
            return False

        phone = getattr(self, 'customer_phone', False) or getattr(self, 'owner_phone', False)
        if not phone:
            self._ts_create_audit_log(
                name=_('Bỏ qua gửi ZNS báo giá'),
                change_scope='notification',
                change_type='notify',
                field_name='zns',
                reason=_('Không tìm thấy số điện thoại khách hàng trên phiếu.'),
            )
            return False

        model = self.env['ir.model']._get('ticket.helpdesk')
        batch = self.env['zalo.zns.batch'].sudo().create({
            'template_id': template.id,
            'origin_model': 'ticket.helpdesk',
        })
        msg = self.env['zalo.zns.message'].sudo().create({
            'batch_id': batch.id,
            'model_id': model.id,
            'record_id': self.id,
            'phone': phone,
            'name': _('Thông báo báo giá - %s') % (order.name or self.display_name),
        })
        msg.action_send_message_zalo_zns()
        self.write({
            'ts_quote_zns_sent': True,
            'ts_quote_zns_sent_at': fields.Datetime.now(),
        })
        self._ts_create_audit_log(
            name=_('Đã tạo ZNS báo giá'),
            change_scope='notification',
            change_type='notify',
            field_name='zns',
            new_value=getattr(msg, 'display_name', msg.name),
            reason=_('Đã tạo ZNS báo giá cho số %s') % phone,
        )
        return True

    def _ts_apply_delivered_serial(self, lot, source=None):
        self.ensure_one()
        if not lot:
            return False
        vals = {
            'replace_serial_number': lot.name,
            'ts_last_serial_sync_at': fields.Datetime.now(),
            'ts_last_serial_sync_note': _('Cập nhật từ phiếu giao %s') % (source or ''),
            'ts_serial_synced': True,
        }
        if 'new_stock_lot_id' in self._fields:
            vals['new_stock_lot_id'] = lot.id
        self.write(vals)
        self._ts_notify_internal_event(
            _('Đã cập nhật serial thay thế'),
            _('Serial thay thế đã được cập nhật tự động thành %(serial)s từ phiếu giao %(source)s.') % {
                'serial': lot.name,
                'source': source or '-',
            },
        )
        self._ts_create_audit_log(
            name=_('Tự động đồng bộ serial từ phiếu giao'),
            change_scope='serial',
            change_type='sync',
            field_name='replace_serial_number',
            new_value=lot.name,
            reason=source,
        )
        return True
