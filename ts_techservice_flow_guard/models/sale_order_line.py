from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    ts_source_order_id = fields.Many2one(
        'sale.order',
        string='Báo giá nguồn',
        copy=False,
        readonly=True,
        index=True,
    )
    ts_source_ticket_id = fields.Many2one(
        'ticket.helpdesk',
        string='Ticket nguồn',
        copy=False,
        readonly=True,
        index=True,
    )

    TRACKED_FIELDS = [
        'product_id',
        'name',
        'product_uom_qty',
        'price_unit',
        'discount',
        'filler_warehouse_id',
        'create_sap',
        'quotation_warranty_term',
    ]
    PRICE_IMPACT_FIELDS = ['product_uom_qty', 'price_unit', 'discount', 'product_id']

    @staticmethod
    def _to_text(value):
        if value is False or value is None:
            return False
        if hasattr(value, 'display_name'):
            return value.display_name
        return str(value)

    def _guard_post_so_edit(self, vals):
        for line in self:
            order = line.order_id
            if not order or not order._ts_is_edit_locked() or order.ts_allow_post_so_price_edit:
                continue
            if self.env.context.get('ts_allow_post_so_edit'):
                continue
            changed = set(vals.keys()).intersection(set(self.TRACKED_FIELDS))
            if changed:
                raise UserError(_(
                    'Báo giá / SO này đã ở giai đoạn sau SO. Hệ thống khóa sửa giá / vật tư. '
                    'Hãy bật "Cho phép sửa báo giá sau SO" hoặc truyền context ts_allow_post_so_edit=True nếu chủ động cho phép.'
                ))

    @api.model
    def _guard_post_so_create(self, vals_list):
        if self.env.context.get('ts_allow_post_so_edit'):
            return
        order_ids = {vals.get('order_id') for vals in vals_list if vals.get('order_id')}
        for order in self.env['sale.order'].browse(list(order_ids)).exists():
            if order._ts_is_edit_locked() and not order.ts_allow_post_so_price_edit:
                raise UserError(_(
                    'Báo giá / SO này đã ở giai đoạn sau SO. Hệ thống khóa tạo mới dòng vật tư. '
                    'Hãy bật "Cho phép sửa báo giá sau SO" hoặc truyền context ts_allow_post_so_edit=True nếu chủ động cho phép.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        self._guard_post_so_create(vals_list)
        lines = super().create(vals_list)
        for line, vals in zip(lines, vals_list):
            if line.display_type or not line.order_id:
                continue
            line.order_id._ts_create_audit_log(
                name=_('Đã tạo dòng báo giá'),
                change_scope='line',
                change_type='create',
                line_id=line.id,
                field_name='line',
                new_value='%s x %s @ %s' % (line.product_id.display_name, line.product_uom_qty, line.price_unit),
            )
            if (
                not self.env.context.get('ts_skip_price_impact')
                and set(vals.keys()).intersection(set(self.PRICE_IMPACT_FIELDS))
            ):
                line.order_id._ts_mark_price_impact(_('Đã thêm dòng vật tư mới.'))
        return lines

    def write(self, vals):
        self._guard_post_so_edit(vals)
        snapshots = {
            line.id: {field: line[field] for field in self.TRACKED_FIELDS if field in vals}
            for line in self
        }
        res = super().write(vals)
        for line in self.filtered(lambda l: not l.display_type and l.order_id):
            changed_fields = []
            for field in self.TRACKED_FIELDS:
                if field not in vals:
                    continue
                old = snapshots.get(line.id, {}).get(field)
                new = line[field]
                if self._to_text(old) == self._to_text(new):
                    continue
                changed_fields.append(field)
                line.order_id._ts_create_audit_log(
                    name=_('Đã cập nhật dòng báo giá'),
                    change_scope='line',
                    change_type='update',
                    line_id=line.id,
                    field_name=field,
                    old_value=self._to_text(old),
                    new_value=self._to_text(new),
                )
            if (
                not self.env.context.get('ts_skip_price_impact')
                and set(changed_fields).intersection(set(self.PRICE_IMPACT_FIELDS))
            ):
                line.order_id._ts_mark_price_impact(
                    _('Đã thay đổi các trường giá / vật tư: %s') % ', '.join(changed_fields)
                )
        return res

    def unlink(self):
        for line in self.filtered(lambda l: not l.display_type and l.order_id):
            order = line.order_id
            if order._ts_is_edit_locked() and not order.ts_allow_post_so_price_edit and not self.env.context.get('ts_allow_post_so_edit'):
                raise UserError(_(
                    'Báo giá / SO này đã ở giai đoạn sau SO. Hệ thống khóa xóa dòng vật tư. '
                    'Hãy bật "Cho phép sửa báo giá sau SO" hoặc truyền context ts_allow_post_so_edit=True nếu chủ động cho phép.'
                ))
            order._ts_create_audit_log(
                name=_('Đã xóa dòng báo giá'),
                change_scope='line',
                change_type='delete',
                line_id=line.id,
                field_name='line',
                old_value='%s x %s @ %s' % (line.product_id.display_name, line.product_uom_qty, line.price_unit),
            )
            order._ts_mark_price_impact(_('Đã xóa dòng vật tư.'))
        return super().unlink()
