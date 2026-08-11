from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'abstract.custom.view']

    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Spare Part")

    onhand_quantity = fields.Float(string='On Hand Quantity', readonly=True)

    @property
    def invisible_fields(self):
        return {
            'tax_id',
            'product_id',
            'price_subtotal',
        }

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Overwrite the Odoo base: Compute the amounts of the SO line.
        Changes: Not use tax.
        """
        super()._compute_amount()
        for line in self:
            line.price_tax = 0
            line.price_total = line.price_subtotal

    @api.depends('product_id', 'product_uom', 'product_uom_qty')
    def _compute_price_unit(self):
        super()._compute_price_unit()
        lines = self.filtered(lambda line: line._use_dat_price_list_price())
        price_items_by_code = self._get_dat_price_items_by_code(lines)
        for line in lines:
            company = line._get_dat_price_company()
            item_code = line._get_dat_price_item_code()
            price_item = price_items_by_code.get((company.id, item_code))
            if not price_item:
                # Keep the standard Odoo/product price when DAT Price List has
                # no matching item. Never replace a valid price with zero.
                continue
            line.price_unit = line._get_dat_price_from_item(price_item)

    def _use_dat_price_list_price(self):
        self.ensure_one()
        is_discount_line = getattr(self, '_is_discount_line', None)
        return (
            self.product_id
            and not self.display_type
            and self.qty_invoiced <= 0
            and not (self.product_id.expense_policy == 'cost' and self.is_expense)
            and not (is_discount_line and is_discount_line())
        )

    def _get_dat_price_items_by_code(self, lines):
        codes_by_company = {}
        for line in lines:
            company = line._get_dat_price_company()
            item_code = line._get_dat_price_item_code()
            if company and item_code:
                codes_by_company.setdefault(company.id, set()).add(item_code)

        price_items_by_code = {}
        for company_id, item_codes in codes_by_company.items():
            company = self.env['res.company'].browse(company_id)
            price_items = self._get_dat_price_items(item_codes, company)
            price_items_by_code.update({
                (company_id, item_code): price_item
                for item_code, price_item in price_items.items()
            })
        return price_items_by_code

    @api.model
    def _get_dat_price_items(self, item_codes, company):
        normalized_codes = {
            (item_code or '').strip().upper()
            for item_code in item_codes
            if (item_code or '').strip()
        }
        if not normalized_codes or not company:
            return {}

        candidate_company_ids = self._get_dat_price_company_candidate_ids(company)
        PriceItem = self.env['dat.price.list.item']
        price_items = PriceItem.search([
            ('company_id', 'in', candidate_company_ids),
            ('item_code', 'in', list(normalized_codes)),
        ])
        items_by_company_code = {
            (item.company_id.id, (item.item_code or '').strip().upper()): item
            for item in price_items
        }

        result = {}
        for item_code in normalized_codes:
            for candidate_company_id in candidate_company_ids:
                price_item = items_by_company_code.get(
                    (candidate_company_id, item_code)
                )
                if price_item:
                    result[item_code] = price_item
                    break

        # Legacy data can belong to a company outside the current branch tree.
        # Use it only when the code is unique, avoiding an arbitrary price when
        # several companies maintain different prices for the same item.
        missing_codes = normalized_codes - result.keys()
        if missing_codes:
            fallback_items = PriceItem.search([
                ('item_code', 'in', list(missing_codes)),
            ])
            fallback_by_code = {}
            for item in fallback_items:
                item_code = (item.item_code or '').strip().upper()
                fallback_by_code.setdefault(item_code, self.env['dat.price.list.item'])
                fallback_by_code[item_code] |= item
            for item_code, items in fallback_by_code.items():
                if len(items) == 1:
                    result[item_code] = items
        return result

    @api.model
    def _get_dat_price_company_candidate_ids(self, company):
        candidate_ids = []

        def add_company_and_parents(candidate):
            visited = set()
            while candidate and candidate.id not in visited:
                visited.add(candidate.id)
                if candidate.id not in candidate_ids:
                    candidate_ids.append(candidate.id)
                candidate = candidate.parent_id

        add_company_and_parents(company)
        add_company_and_parents(self.env.company)
        main_company = self.env.ref('base.main_company', raise_if_not_found=False)
        add_company_and_parents(main_company)
        return candidate_ids

    def _get_dat_price_from_item(self, price_item):
        self.ensure_one()
        target_currency = self.currency_id or self.order_id.currency_id
        if not target_currency or price_item.currency_id == target_currency:
            return price_item.price

        company = self._get_dat_price_company()
        conversion_date = fields.Date.to_date(self.order_id.date_order)
        return price_item.currency_id._convert(
            price_item.price,
            target_currency,
            company,
            conversion_date or fields.Date.context_today(self),
            round=False,
        )

    def _apply_dat_price_list(self, only_zero=False):
        lines = self.filtered(lambda line: line._use_dat_price_list_price())
        price_items_by_code = self._get_dat_price_items_by_code(lines)
        updated_count = 0
        missing_count = 0
        for line in lines:
            currency = line.currency_id or line.order_id.currency_id
            if only_zero and currency and not currency.is_zero(line.price_unit):
                continue

            company = line._get_dat_price_company()
            item_code = line._get_dat_price_item_code()
            price_item = price_items_by_code.get((company.id, item_code))
            if not price_item:
                missing_count += 1
                continue

            new_price = line._get_dat_price_from_item(price_item)
            if currency and currency.is_zero(line.price_unit - new_price):
                continue
            if not currency and line.price_unit == new_price:
                continue
            line.price_unit = new_price
            updated_count += 1
        return updated_count, missing_count

    def _get_dat_price_company(self):
        self.ensure_one()
        return self.company_id or self.order_id.company_id or self.env.company

    def _get_dat_price_item_code(self):
        self.ensure_one()
        return (self.product_id.default_code or '').strip().upper()
