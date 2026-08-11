from odoo import _, fields, models
from odoo.exceptions import UserError


class StandardQuotationExportWizard(models.TransientModel):
    _name = 'standard.quotation.export.wizard'
    _description = 'Tùy chọn xuất phiếu báo giá'

    sale_order_ids = fields.Many2many(
        'sale.order',
        string='Báo giá',
        required=True,
    )
    export_mode = fields.Selection(
        selection=[
            ('summary', 'Sản phẩm chính và phí dịch vụ sửa chữa'),
            ('detailed', 'Chi tiết từng sản phẩm, linh kiện'),
        ],
        string='Nội dung xuất',
        required=True,
        default='summary',
    )

    def action_export_pdf(self):
        self.ensure_one()
        orders = self.sale_order_ids.exists()
        if not orders:
            raise UserError(_('Vui lòng chọn ít nhất một báo giá để xuất file.'))

        orders._validate_standard_quotation_export()
        report = self.env.ref(
            'dat_service_workflow_extension.action_report_standard_quotation'
        ).with_context(standard_quotation_export_mode=self.export_mode)
        return report.report_action(orders)
