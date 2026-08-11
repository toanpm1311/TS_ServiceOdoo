from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    sap_is_discount = fields.Selection(
        string='Is Discount',
        selection=[
            ('BT', 'Normal'),
            ('BK', 'Add-on'),
            ('KM', 'Discount')
        ],
        default='BT',
        required=True)  # U_isDiscount
    sap_wmonth = fields.Integer(
        string='Warranty (Months)', default=0)  # U_WarrTime
    sap_discount_amount = fields.Float(
        string='Discount Amount',
        compute='_compute_sap_discount_amount')  # U_DiscAmt
    filler_warehouse_id = fields.Many2one(
        'stock.warehouse', string='Filler Warehouse', store=True, readonly=False)
    
    wf_external_id = fields.Char(
        related='order_id.wf_external_id',
        string='Workflow External ID',
        readonly=True
    )

    create_sap = fields.Boolean(string='Create in SAP', default=True)
    sap_dxvt_created = fields.Boolean(
        string='Đã tạo ĐXVT',
        default=False,
        copy=False,
        readonly=True,
    )

    @api.depends('price_unit', 'discount')
    def _compute_sap_discount_amount(self):
        for rec in self:
            rec.sap_discount_amount = rec.price_unit * rec.discount / 100

    @api.model
    def create(self, vals):
        order = self.env['sale.order'].browse(vals.get('order_id'))
        wf_external_id = order.wf_external_id or vals.get('wf_external_id')
        if wf_external_id == 'workflow_1' and not vals.get('filler_warehouse_id'):
            raise ValidationError(_("You need to enter Filler Warehouse for the products in the order details."))
        return super().create(vals)
