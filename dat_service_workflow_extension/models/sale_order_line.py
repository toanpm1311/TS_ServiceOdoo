from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    main_product_code = fields.Char(string='M\u00e3 s\u1ea3n ph\u1ea9m ch\u00ednh', related='order_id.main_product_code', readonly=True)
    manufacturer_warranty_month = fields.Integer(string='B\u1ea3o h\u00e0nh h\u00e3ng (th\u00e1ng)')
    quotation_warranty_term = fields.Char(
        string='Thời hạn bảo hành linh kiện',
        help='Nhập tay thời hạn bảo hành thể hiện trên phiếu báo giá, ví dụ: 6 tháng. Có thể để trống.',
    )
    manufacturer_warranty_end_date = fields.Datetime(
        string='Ng\u00e0y h\u1ebft h\u1ea1n b\u1ea3o h\u00e0nh h\u00e3ng',
        compute='_compute_manufacturer_warranty_end_date',
    )

    @api.depends(
        'manufacturer_warranty_month',
        'product_id',
        'order_id.ticket_id.stock_lot_id.warranty_start_date',
    )
    def _compute_manufacturer_warranty_end_date(self):
        for line in self:
            start_date = line.order_id.ticket_id.stock_lot_id.warranty_start_date
            months = line.manufacturer_warranty_month
            line.manufacturer_warranty_end_date = start_date + relativedelta(months=months) if start_date and months else False

    @api.onchange('product_id')
    def _onchange_product_id_service_extension(self):
        for line in self:
            if line.product_id:
                if line.order_id.ticket_id and line.order_id.wf_external_id == 'workflow_1':
                    line.sap_wmonth = 0
                    line.manufacturer_warranty_month = 0
                else:
                    line.manufacturer_warranty_month = line.product_id.sap_wmonth_dist or 0
                line.onhand_quantity = line.product_id.qty_available
