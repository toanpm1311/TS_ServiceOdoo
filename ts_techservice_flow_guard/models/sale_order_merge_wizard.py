from odoo import _, fields, models
from odoo.exceptions import UserError


class TsSaleOrderMergeWizard(models.TransientModel):
    _name = 'ts.sale.order.merge.wizard'
    _description = 'Gộp báo giá Techservice'

    base_order_id = fields.Many2one(
        'sale.order',
        string='Báo giá nguồn chính',
        required=True,
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
        identities = {
            self._get_order_customer_contact_identity(order)
            for order in orders
        }
        if len(identities) > 1:
            raise UserError(_(
                'Chỉ được gộp các báo giá trùng tên khách hàng và người liên hệ.'
            ))

        same_record_fields = (
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

    def _get_order_customer_contact_identity(self, order):
        ticket = order.ticket_id
        if hasattr(order, '_get_standard_quotation_customer_name'):
            customer_name = order._get_standard_quotation_customer_name()
        elif ticket and hasattr(ticket, '_service_owner_company_name'):
            customer_name = ticket._service_owner_company_name()
        else:
            customer_name = order.partner_id.name

        contact_name = (
            ticket.owner_id.name
            if ticket and ticket.owner_id
            else order.partner_id.name
        )
        return ((customer_name or '').strip(), (contact_name or '').strip())

    def _prepare_merged_order_copy_values(self, primary_order, source_orders):
        seq_date = (
            fields.Datetime.context_timestamp(
                primary_order,
                fields.Datetime.to_datetime(primary_order.date_order),
            )
            if primary_order.date_order
            else None
        )
        new_name = self.env['ir.sequence'].with_company(
            primary_order.company_id
        ).next_by_code('sale.order', sequence_date=seq_date) or _('New')
        source_names = ', '.join(source_orders.mapped('name'))
        values = {
            'name': new_name,
            'state': 'draft',
            'status': 'draft',
            'sap_status': False,
            'sap_is_create_so': False,
            'cancel_reason': False,
            'reject_reason': False,
            'origin': source_names,
            'client_order_ref': _('Gộp từ %(sources)s') % {
                'sources': source_names,
            },
        }
        reset_values = {
            'locked': False,
            'ts_merged_into_order_id': False,
            'ts_pair_origin_order_id': False,
            'ts_pair_role': 'primary',
            'ts_bound_stage': 'normal',
            'ts_price_impact_review_required': False,
            'ts_last_price_change_at': False,
            'ts_last_price_change_note': False,
            'service_quotation_status': 'waiting_quotation',
            'delivery_time_confirmed': False,
            'delivery_confirmed_datetime': False,
            'ts_main_so_doc_number': False,
            'ts_main_dxvt_doc_number': False,
            'ts_lt_so_doc_number': False,
            'ts_lt_dxvt_doc_number': False,
            'ts_split_doc_note': False,
            'ts_split_dxvt_note': False,
            'ts_split_sap_doc_state': False,
            'sap_dxvt_order_number': False,
            'sap_itr_number': False,
            'sap_dxvt_doc_number': False,
        }
        values.update({
            field_name: value
            for field_name, value in reset_values.items()
            if field_name in primary_order._fields
        })
        return values

    def action_merge_orders(self):
        self.ensure_one()
        primary_order = self.base_order_id.exists()
        additional_orders = self.merge_order_ids.exists() - primary_order
        if not primary_order:
            raise UserError(_('Vui lòng chọn báo giá nguồn chính.'))

        self._validate_orders(primary_order, additional_orders)
        source_orders = primary_order | additional_orders
        copy_values = self._prepare_merged_order_copy_values(
            primary_order, source_orders
        )
        merged_order = primary_order.with_context(
            ts_allow_post_so_edit=True,
            ts_skip_price_impact=True,
            skip_procurement=True,
        ).copy(copy_values)

        merged_order.order_line.filtered(
            lambda line: not line.ts_source_ticket_id
        ).with_context(
            ts_allow_post_so_edit=True,
            ts_skip_price_impact=True,
        ).write({
            'ts_source_order_id': primary_order.id,
            'ts_source_ticket_id': primary_order.ticket_id.id,
        })

        next_sequence = max(merged_order.order_line.mapped('sequence') or [0])
        for source in additional_orders.sorted(key=lambda order: order.id):
            for line in source.order_line.sorted(
                key=lambda order_line: (order_line.sequence, order_line.id)
            ):
                next_sequence += 10
                copy_values = {
                    'order_id': merged_order.id,
                    'sequence': next_sequence,
                    'ts_source_order_id': source.id,
                    'ts_source_ticket_id': source.ticket_id.id,
                }
                if line.display_type and not line.filler_warehouse_id:
                    copy_values['filler_warehouse_id'] = (
                        source.filler_warehouse_id
                        or merged_order.filler_warehouse_id
                    ).id
                line.with_context(
                    ts_allow_post_so_edit=True,
                    ts_skip_price_impact=True,
                    skip_procurement=True,
                ).copy(copy_values)

        merged_order.order_line.with_context(
            ts_allow_post_so_edit=True,
            ts_skip_price_impact=True,
        )._apply_dat_price_list(only_zero=True)

        tickets = (
            source_orders.mapped('ts_quotation_ticket_ids')
            | source_orders.mapped('ticket_id')
        )
        merged_order.with_context(
            ts_allow_post_so_edit=True,
            ts_skip_merge_sync=True,
        ).write({
            'ts_quotation_ticket_ids': [fields.Command.set(tickets.ids)],
        })

        source_names = ', '.join(source_orders.mapped('name'))
        merge_note = _(
            'Đã tạo báo giá tổng mới %(target)s từ các báo giá %(sources)s. '
            'Báo giá tổng có %(line_count)s dòng và tổng thanh toán %(amount)s.'
        ) % {
            'sources': source_names,
            'target': merged_order.name,
            'line_count': len(merged_order.order_line.filtered(
                lambda line: not line.display_type
            )),
            'amount': merged_order.amount_total,
        }
        merged_order.message_post(body=merge_note)
        merged_order._ts_create_audit_log(
            name=_('Đã tạo báo giá tổng'),
            change_scope='order',
            change_type='create',
            field_name='origin',
            new_value=source_names,
            reason=merge_note,
        )

        self.summary = merge_note
        return {
            'type': 'ir.actions.act_window',
            'name': _('Báo giá tổng'),
            'res_model': 'sale.order',
            'res_id': merged_order.id,
            'view_mode': 'form',
            'target': 'current',
        }
