import io
import base64
from odoo import api, fields, models, _
from xlsxwriter import Workbook
from ..models.common_utils_mixin import CommonUtilsMixin


class RepairSalesReportWizardLine(models.TransientModel):
    _name = 'repair.sales.report.wizard.line'
    _description = 'Repair Sales Report Wizard Line'

    wizard_id       = fields.Many2one(
        'repair.sales.report.wizard',
        ondelete='cascade',
        required=True,
    )
    sequence        = fields.Integer('No.', readonly=True)
    date_order      = fields.Datetime('Date', readonly=True)
    ticket_id       = fields.Many2one('ticket.helpdesk', 'Ticket', readonly=True)
    order_id        = fields.Many2one('sale.order',   'Sales Order', readonly=True)
    product_code    = fields.Char('Product Code', readonly=True)
    product_name    = fields.Char('Product Name', readonly=True)
    product_uom = fields.Many2one('uom.uom', 'UoM', readonly=True)
    product_uom_qty = fields.Float('Quantity', readonly=True)
    price_unit      = fields.Float('Unit Price', readonly=True)
    price_total     = fields.Float('Total', readonly=True)
    customer_id     = fields.Many2one('res.partner','Customer', readonly=True)
    sale_person_id  = fields.Many2one('hr.employee',  'Salesperson', readonly=True)
    business_unit   = fields.Char('BU', readonly=True)
    company_id      = fields.Many2one('res.company','Branch', readonly=True)
    month           = fields.Integer('Month', readonly=True)

class RepairSalesWizard(models.TransientModel, CommonUtilsMixin):
    _name = 'repair.sales.report.wizard'
    _description = 'Repair Sales Report'

    date_from = fields.Date('From Date')
    date_to = fields.Date('To Date')
    customer_id = fields.Many2one('res.partner', 'Customer')
    ticket_id = fields.Many2one('ticket.helpdesk', 'Ticket')
    sale_person_id = fields.Many2one('hr.employee', 'Salesperson')

    def _compute_display_name(self):
        for record in self:
            record.display_name = _("Repair Sales Report")

    line_ids = fields.One2many(
        'repair.sales.report.wizard.line',
        'wizard_id',
        string='Lines',
        compute='_compute_lines',
        readonly=True,
        store=True,
    )

    @api.depends('date_from', 'date_to', 'customer_id', 'ticket_id', 'sale_person_id')
    def _compute_lines(self):
        for wiz in self:
            # xóa cũ
            wiz.line_ids = [(5, 0, 0)]
            domain = wiz._get_domain()
            reps = self.env['repair.sales.report'].search(domain, order='date_order desc')
            lines = []
            for idx, rec in enumerate(reps, start=1):
                lines.append((0, 0, {
                    'sequence': idx,
                    'date_order': rec.date_order,
                    'ticket_id': rec.ticket_id.id,
                    'order_id': rec.order_id.id,
                    'product_code': rec.product_code,
                    'product_name': rec.product_name,
                    'product_uom': rec.product_uom.id,
                    'product_uom_qty': rec.product_uom_qty,
                    'price_unit': rec.price_unit,
                    'price_total': rec.price_total,
                    'customer_id': rec.customer_id.id,
                    'sale_person_id': rec.sale_person_id.id,
                    'business_unit': rec.business_unit,
                    'company_id': rec.company_id.id,
                    'month': rec.month,
                }))
            wiz.line_ids = lines

    def _get_domain(self):
        self.ensure_one()
        dom = []
        if self.date_from:      dom.append(('date_order', '>=', self.date_from))
        if self.date_to:        dom.append(('date_order', '<=', self.date_to))
        if self.customer_id:    dom.append(('customer_id', '=', self.customer_id.id))
        if self.ticket_id:      dom.append(('ticket_id', '=', self.ticket_id.id))
        if self.sale_person_id: dom.append(('sale_person_id', '=', self.sale_person_id.id))
        return dom

    def action_export_xlsx(self):
        self.ensure_one()
        headers = ['STT', 'Ngày', 'Mã phiếu', 'Số lệnh SO', 'Mã SP/DV', 'Tên SP/DV', 'ĐVT', 'SL',
                   'Đơn giá', 'Thành tiền', 'Tên Khách Hàng', 'NVKD', 'Ngành', 'Khu vực', 'Tháng']
        output = io.BytesIO()
        wb = Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('Report')
        ws.set_column(0, len(headers) - 1, 18)
        filters = [
            (_('From Date'), self.date_from.strftime('%d/%m/%Y') if self.date_from else ''),
            (_('To Date'), self.date_to.strftime('%d/%m/%Y') if self.date_to else ''),
            (_('Customer'), self.customer_id.display_name or ''),
            (_('Ticket'), self.ticket_id.name or ''),
            (_('Salesperson'), self.sale_person_id.name or ''),
        ]
        header_row, header_format = self._write_xlsx_report_header(
            wb, ws, _('Repair Sales Report'), len(headers), filters
        )
        for col, h in enumerate(headers):
            ws.write(header_row, col, h, header_format)
        for row_idx, rec in enumerate(self.line_ids, start=header_row + 1):
            row = [
                row_idx - header_row,
                self.convert_to_user_tz(rec.date_order).strftime('%Y-%m-%d %H:%M:%S') or '',
                rec.ticket_id.name or '',
                rec.order_id.name or '',
                rec.product_code or '',
                rec.product_name or '',
                rec.product_uom.name or '',
                rec.product_uom_qty,
                rec.price_unit,
                rec.price_total,
                rec.customer_id.name or '',
                rec.sale_person_id.name or '',
                rec.business_unit or '',
                rec.company_id.name or '',
                rec.month,
            ]
            for col_idx, val in enumerate(row):
                ws.write(row_idx, col_idx, val)
        wb.close()
        data = output.getvalue()
        attachment = self.env['ir.attachment'].create({
            'name': 'repair_sales_report.xlsx',
            'datas': base64.b64encode(data),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self'
        }
