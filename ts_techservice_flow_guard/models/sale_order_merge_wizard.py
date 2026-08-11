from odoo import _, fields, models
from odoo.exceptions import UserError


class TsSaleOrderMergeWizard(models.TransientModel):
    _name = 'ts.sale.order.merge.wizard'
    _description = 'Gộp báo giá Techservice'

    base_order_id = fields.Many2one(
        'sale.order',
        string='Báo giá tổng',
        required=True,
        domain="[('state', '=', 'draft'), ('status', '=', 'draft'), "
               "('sap_status', '=', False), ('ts_merged_into_order_id', '=', False)]",
    )
    merge_order_ids = fields.Many2many(
        'sale.order',
        string='Báo giá cần gộp',
        required=True,
    )
    customer_id = fields.Many2one(
        'res.partner',
        string='Khách hàng',
        related='base_order_id.ts_merge_customer_id',
        readonly=True,
    )
    summary = fields.Text(string='Kết quả', readonly=True)

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_orders = self.env['sale.order'].browse(
            self.env.context.get('active_ids', [])
        ).exists()
        base_order = active_orders[:1]
        if not base_order:
            base_order = self.env['sale.order'].browse(
                self.env.context.get('active_id')
            ).exists()

        if base_order and 'base_order_id' in fields_list:
            res['base_order_id'] = base_order.id
        if active_orders and 'merge_order_ids' in fields_list:
            res['merge_order_ids'] = [
                fields.Command.set((active_orders - base_order).ids)
            ]
        return res

    def _validate_orders(self, target, sources):
        orders = target | sources
        if not sources:
            raise UserError(_('Vui lòng chọn ít nhất một báo giá nguồn để gộp.'))
        if any(not order.ticket_id for order in orders):
            raise UserError(_('Chỉ được gộp các báo giá được tạo từ ticket Techservice.'))
        if any(order.state != 'draft' or order.status != 'draft' for order in orders):
            raise UserError(_('Chỉ được gộp các báo giá còn ở trạng thái nháp/chưa gửi.'))
        if any(order.sap_status for order in orders):
            raise UserError(_('Không thể gộp báo giá đã tạo chứng từ trên SAP.'))
        if any(order.ts_merged_into_order_id for order in orders):
            raise UserError(_('Danh sách có báo giá đã được gộp trước đó.'))
        if any(order.ts_merged_source_order_ids for order in sources):
            raise UserError(
                _('Không thể dùng một báo giá tổng khác làm báo giá nguồn.')
            )

        same_record_fields = (
            ('ts_merge_customer_id', _('khách hàng sở hữu')),
            ('company_id', _('công ty')),
            ('currency_id', _('tiền tệ')),
        )
        for field_name, label in same_record_fields:
            if len({order[field_name].id for order in orders}) > 1:
                raise UserError(
                    _('Các báo giá phải có cùng %(field)s.') % {'field': label}
                )

        same_value_fields = (('wf_external_id', _('workflow')),)
        for field_name, label in same_value_fields:
            if len(set(orders.mapped(field_name))) > 1:
                raise UserError(
                    _('Các báo giá phải có cùng %(field)s.') % {'field': label}
                )

    def action_merge_orders(self):
        self.ensure_one()
        target = self.base_order_id.exists()
        sources = self.merge_order_ids.exists() - target
        if not target:
            raise UserError(_('Vui lòng chọn báo giá tổng.'))

        self._validate_orders(target, sources)

        target.order_line.filtered(
            lambda line: not line.ts_source_ticket_id
        ).with_context(
            ts_allow_post_so_edit=True,
            ts_skip_price_impact=True,
        ).write({
            'ts_source_order_id': target.id,
            'ts_source_ticket_id': target.ticket_id.id,
        })

        next_sequence = max(target.order_line.mapped('sequence') or [0])
        for source in sources.sorted(key=lambda order: order.id):
            for line in source.order_line.sorted(
                key=lambda order_line: (order_line.sequence, order_line.id)
            ):
                next_sequence += 10
                copy_values = {
                    'order_id': target.id,
                    'sequence': next_sequence,
                    'ts_source_order_id': source.id,
                    'ts_source_ticket_id': source.ticket_id.id,
                }
                if line.display_type and not line.filler_warehouse_id:
                    copy_values['filler_warehouse_id'] = (
                        source.filler_warehouse_id or target.filler_warehouse_id
                    ).id
                line.with_context(
                    ts_allow_post_so_edit=True,
                    ts_skip_price_impact=True,
                ).copy(copy_values)

        target.order_line.with_context(
            ts_allow_post_so_edit=True,
            ts_skip_price_impact=True,
        )._apply_dat_price_list(only_zero=True)

        tickets = (
            target.ts_quotation_ticket_ids
            | target.ticket_id
            | sources.mapped('ticket_id')
        )
        target.with_context(ts_allow_post_so_edit=True).write({
            'ts_quotation_ticket_ids': [fields.Command.set(tickets.ids)],
        })

        sources.with_context(
            disable_cancel_warning=True,
            ts_allow_post_so_edit=True,
            ts_skip_merge_sync=True,
        ).action_cancel()
        sources.with_context(
            ts_allow_post_so_edit=True,
            ts_skip_merge_sync=True,
        ).write({
            'ts_merged_into_order_id': target.id,
            'status': target.status,
        })

        source_names = ', '.join(sources.mapped('name'))
        merge_note = _(
            'Đã gộp các báo giá %(sources)s vào báo giá tổng %(target)s. '
            'Báo giá tổng có %(line_count)s dòng và tổng thanh toán %(amount)s.'
        ) % {
            'sources': source_names,
            'target': target.name,
            'line_count': len(target.order_line.filtered(lambda line: not line.display_type)),
            'amount': target.amount_total,
        }
        target.message_post(body=merge_note)
        for source in sources:
            source.message_post(
                body=_('Báo giá đã được gộp vào %s.') % target.name
            )
            source._ts_create_audit_log(
                name=_('Đã gộp vào báo giá tổng'),
                change_scope='order',
                change_type='update',
                field_name='ts_merged_into_order_id',
                new_value=target.name,
                reason=merge_note,
            )
        target._ts_create_audit_log(
            name=_('Đã tạo báo giá tổng'),
            change_scope='order',
            change_type='update',
            field_name='ts_merged_source_order_ids',
            new_value=source_names,
            reason=merge_note,
        )

        self.summary = merge_note
        return {
            'type': 'ir.actions.act_window',
            'name': _('Báo giá tổng'),
            'res_model': 'sale.order',
            'res_id': target.id,
            'view_mode': 'form',
            'target': 'current',
        }
