from odoo import fields, models


class TechserviceAuditLog(models.Model):
    _name = 'ts.techservice.audit.log'
    _description = 'Nhật ký kiểm soát Techservice'
    _order = 'change_date desc, id desc'

    name = fields.Char(string='Mô tả', required=True)
    order_id = fields.Many2one('sale.order', string='Báo giá / SO', ondelete='cascade', index=True)
    ticket_id = fields.Many2one('ticket.helpdesk', string='Phiếu', ondelete='set null', index=True)
    line_id = fields.Many2one('sale.order.line', string='Dòng đơn hàng', ondelete='set null')
    change_scope = fields.Selection([
        ('order', 'Đơn hàng'),
        ('line', 'Dòng đơn hàng'),
        ('notification', 'Thông báo'),
        ('serial', 'Số serial'),
        ('workflow', 'Luồng xử lý'),
    ], string='Phạm vi', default='order', required=True)
    change_type = fields.Selection([
        ('create', 'Tạo mới'),
        ('update', 'Cập nhật'),
        ('delete', 'Xóa'),
        ('status', 'Trạng thái'),
        ('guard', 'Chặn rule'),
        ('notify', 'Thông báo'),
        ('sync', 'Đồng bộ'),
    ], string='Loại thay đổi', default='update', required=True)
    field_name = fields.Char(string='Trường')
    old_value = fields.Text(string='Giá trị cũ')
    new_value = fields.Text(string='Giá trị mới')
    reason = fields.Text(string='Lý do')
    change_date = fields.Datetime(string='Thời điểm thay đổi', default=fields.Datetime.now, required=True)
    changed_by = fields.Many2one('res.users', string='Người thay đổi', default=lambda self: self.env.user, required=True)
