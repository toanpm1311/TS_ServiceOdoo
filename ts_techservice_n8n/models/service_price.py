from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ServicePrice(models.Model):
    _name = 'ts.service.price'
    _description = 'Service price mapping by equipment model'
    _rec_name = 'main_product_id'
    _check_company_auto = True

    main_product_id = fields.Many2one('product.product', string='Model thiết bị', required=True, check_company=True)
    service_product_id = fields.Many2one(
        'product.product', string='Dịch vụ', required=True, check_company=True,
        domain="[('detailed_type', '=', 'service')]",
    )
    price_item_id = fields.Many2one('dat.price.list.item', string='Dòng bảng giá DAT', required=True, check_company=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='price_item_id.currency_id')
    price = fields.Monetary(related='price_item_id.price', string='Giá dịch vụ')

    _sql_constraints = [
        ('model_service_company_unique', 'unique(main_product_id, service_product_id, company_id)',
         'Mỗi model và dịch vụ chỉ có một dòng giá trong một công ty.'),
    ]

    @api.constrains('service_product_id')
    def _check_service_product(self):
        for mapping in self:
            if mapping.service_product_id.detailed_type != 'service':
                raise ValidationError(_('Sản phẩm dịch vụ phải có loại Dịch vụ.'))


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _ts_service_mapping(self):
        self.ensure_one()
        if not self.order_id.ticket_id or self.product_id.detailed_type != 'service':
            return self.env['ts.service.price']
        return self.env['ts.service.price'].search([
            ('main_product_id', '=', self.order_id.main_product_id.id),
            ('service_product_id', '=', self.product_id.id),
            ('company_id', '=', self.order_id.company_id.id),
            ('price_item_id.active', '=', True),
        ], limit=1)

    def _ts_mapped_service_price(self, mapping):
        self.ensure_one()
        price = self._get_dat_price_from_item(mapping.price_item_id)
        return self.product_id.uom_id._compute_price(price, self.product_uom)

    @api.depends('product_id', 'product_uom', 'product_uom_qty', 'order_id.main_product_id', 'order_id.company_id',
                 'order_id.currency_id', 'order_id.date_order')
    def _compute_price_unit(self):
        super()._compute_price_unit()
        for line in self:
            if not line._use_dat_price_list_price() or line.product_id.detailed_type != 'service':
                continue
            mapping = line._ts_service_mapping()
            if mapping:
                line.price_unit = line._ts_mapped_service_price(mapping)

    def _apply_dat_price_list(self, only_zero=False):
        mappings = {line.id: line._ts_service_mapping() for line in self if line._use_dat_price_list_price()}
        mapped_lines = self.filtered(lambda line: mappings.get(line.id))
        others = self - mapped_lines
        updated, missing = super(SaleOrderLine, others)._apply_dat_price_list(only_zero=only_zero)
        for line in mapped_lines:
            currency = line.currency_id or line.order_id.currency_id
            if only_zero and not currency.is_zero(line.price_unit):
                continue
            price = line._ts_mapped_service_price(mappings[line.id])
            if not currency.is_zero(price - line.price_unit):
                line.price_unit = price
                updated += 1
        return updated, missing
