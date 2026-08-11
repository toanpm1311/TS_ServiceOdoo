from odoo import api, fields, models, tools

SAP_PRODUCT_TEMPLATE_FIELDS = {
    'name',
    'sale_delay',
    'tracking',
    'qty_available',
    'default_code',
    'sap_group_code',
    'categ_id',
    'sap_group_name',
    'sap_product_line',
    'sap_product_family',
    'sap_brand',
    'sap_business_unit',
    'active',
    'sap_man_ser_num',
    'sap_serial_num',
    'sap_model',
    'sap_wmonth',
    'description',
    'sap_wmonth_dist',
    'sap_ale_expiration',
    'sap_uom',
    'uom_id',
    'sap_uom_po',
    'sap_uom_so',
    'uom_so_id',
    'sap_costing_system',
    'sap_toleran_day',
    'sap_code_po',
    'sap_create_date',
    'sap_update_date',
    'uom_po_id',
    'business_unit_id',
    'list_price',
}


class ProductTemplate(models.Model):
    """
    Odoo fields was used for SAP includes:
    - name: ItemName
    - uom_id: Computed from sap_uom (InvntryUom)
    - uom_po_id: Computed from sap_uom_po (BuyUnitMsr)
    - sale_delay: LeadTime
    - tracking: Computed from sap_man_ser_num (ManSerNum)
    - active: Valid For
    - qty_available: Quantity
    - categ_id: Computed from sap_group_code (ItmsGrpCod)
    - description: ItemNote
    - default_code: ItemCode
    """
    _name = 'product.template'
    _inherit = ['product.template', 'abstract.custom.view']

    @tools.ormcache()
    def _get_default_category_id(self):
        # Deletion forbidden (at least through unlink)
        return self.env.ref('dat_product.product_category_default')

    # SAP fields
    sap_group_code = fields.Integer("Group Code")
    sap_group_name = fields.Char("Group Name")
    sap_product_line = fields.Char("Product Line")
    sap_product_family = fields.Char("Product Family")
    sap_brand = fields.Char("Brand")
    sap_business_unit = fields.Char("Business Unit (SAP)")
    active = fields.Boolean("Valid For")
    sap_man_ser_num = fields.Boolean("Managed by Serial?")
    sap_serial_num = fields.Char("Serial Number")
    sap_model = fields.Char("Model Code")
    description = fields.Text("Note")
    sap_wmonth = fields.Integer("Warranty (Months)")
    sap_wmonth_dist = fields.Integer("Distributor Warranty (Months)")
    sap_ale_expiration = fields.Integer("Ale Expiration (Months)")
    sap_uom = fields.Char("Inventory UoM")
    uom_id = fields.Many2one(
        'uom.uom', compute='_compute_uom_id', readonly=False, store=True)
    sap_uom_po = fields.Char("Purchase UoM")
    sap_uom_so = fields.Char("Sale UoM")
    uom_so_id = fields.Many2one(
        'uom.uom', 'Sale UoM',
        compute='_compute_uom_so_id',
        required=True,
        readonly=False,
        store=True,
        default=lambda self: self._get_default_uom_id(),
        help="Default unit of measure used for sale orders. It must be in the same category as the default unit of measure.",
    )
    uom_po_id = fields.Many2one(
        'uom.uom', precompute=False, default=lambda self: self._get_default_uom_id())
    sap_costing_system = fields.Char("Costing System")
    sap_toleran_day = fields.Integer("Delivery Tolerance (Days)")
    sap_code_po = fields.Char("PO Code")
    sap_create_date = fields.Datetime(string="Create Date")
    sap_update_date = fields.Datetime(string="Update Date")
    categ_id = fields.Many2one(
        string='Product Group', default=_get_default_category_id, store=True)
    business_unit_id = fields.Many2one(
        'product.business.unit', string='Business Unit', copy=False,
        help="Sinh ra từ giá trị của sap_business_unit")

    detailed_type = fields.Selection(default='product')

    is_spare_part = fields.Boolean('Is Spare Part', default=False)

    def _compute_business_unit(self):
        """Dựa vào sap_business_unit tìm hoặc tạo record bên product.business.unit."""
        bu_model = self.env['product.business.unit'].sudo()
        for tmpl in self:
            code = tmpl.sap_business_unit and tmpl.sap_business_unit.strip()
            if code:
                bu = bu_model.search([('code', '=', code)], limit=1)
                if not bu:
                    bu = bu_model.create({
                        'code': code,
                        'name': code,
                    })
                tmpl.business_unit_id = bu.id
            else:
                tmpl.business_unit_id = False

    @api.onchange('sap_business_unit')
    def _onchange_sap_business_unit(self):
        self._compute_business_unit()

    def _compute_categ_id(self):
        for rec in self:
            if not rec.sap_group_code:
                continue
            category = self.env['product.category'].search(
                [('sap_code', '=', rec.sap_group_code)], limit=1)
            if not category:
                continue
            rec.categ_id = category.id

    @api.onchange('sap_group_code')
    def _onchange_categ_id(self):
        self._compute_categ_id()

    @api.model
    def dat_create_missing_product_variants(self):
        self.env.cr.execute("""
            SELECT product_template.id
              FROM product_template
         LEFT JOIN product_product
                ON product_product.product_tmpl_id = product_template.id
             WHERE product_template.active IS TRUE
               AND product_template.type IN ('consu', 'product')
          GROUP BY product_template.id
            HAVING COUNT(product_product.id) = 0
        """)
        template_ids = [row[0] for row in self.env.cr.fetchall()]
        templates = self.with_context(active_test=False).browse(template_ids)
        for template in templates:
            product = self.env['product.product']._dat_get_or_create_variant_from_template(template)
            if product and not product.active:
                product.active = True

    @api.depends('type', 'sap_man_ser_num')
    def _compute_tracking(self):
        super()._compute_tracking()
        for rec in self:
            if rec.sap_man_ser_num:
                rec.tracking = 'serial'

    @api.depends('sap_uom')
    def _compute_uom_id(self):
        for rec in self:
            unit_category = self.env.ref('uom.product_uom_categ_unit')
            if not rec.sap_uom or not unit_category:
                continue
            uom = self.env['uom.uom'].search(
                [('category_id', '=', unit_category.id), ('name', '=ilike', rec.sap_uom)], limit=1)
            if uom:
                rec.uom_id = uom.id

    @api.depends('uom_id', 'sap_uom_po')
    def _compute_uom_po_id(self):
        super()._compute_uom_po_id()
        for rec in self:
            unit_category = self.env.ref('uom.product_uom_categ_unit')
            if not rec.sap_uom_po or rec.sap_uom_po == rec.uom_po_id.name or not unit_category:
                continue
            new_po_uom = self.env['uom.uom'].search(
                [('category_id', '=', unit_category.id), ('name', '=ilike', rec.sap_uom_po)], limit=1)
            if new_po_uom:
                rec.uom_po_id = new_po_uom.id

    @api.depends('uom_id', 'sap_uom_so')
    def _compute_uom_so_id(self):
        for rec in self:
            unit_category = self.env.ref('uom.product_uom_categ_unit')
            # If no sap_uom_so, set uom_so_id to uom_id (only if uom_so_id is not set)
            if not rec.sap_uom_so:
                if not rec.uom_so_id:
                    rec.uom_so_id = rec.uom_id
            # If sap_uom_so is set and different from uom_so_id.name, search for the uom
            elif rec.sap_uom_so != rec.uom_so_id.name and unit_category:
                new_so_uom = self.env['uom.uom'].search(
                    [('category_id', '=', unit_category.id), ('name', '=ilike', rec.sap_uom_so)], limit=1)
                if new_so_uom:
                    rec.uom_so_id = new_so_uom.id
            else:
                rec.uom_so_id = rec.uom_so_id or False

    @property
    def invisible_fields(self):
        return self._fields.keys() - SAP_PRODUCT_TEMPLATE_FIELDS

    @property
    def readonly_fields(self):
        return self._fields.keys() - {'list_price'}

class ProductProduct(models.Model):
    """
    Odoo fields was used for SAP includes:
    - name: ItemName
    - uom_id: Computed from sap_uom (InvntryUom)
    - uom_po_id: Computed from sap_uom_po (BuyUnitMsr)
    - sale_delay: LeadTime
    - tracking: Computed from sap_man_ser_num (ManSerNum)
    - active: Valid For
    - qty_available: Quantity
    - categ_id: Computed from sap_group_code (ItmsGrpCod)
    - description: ItemNote
    - default_code: ItemCode
    """
    _name = 'product.product'
    _inherit = ['product.product', 'abstract.custom.view']

    @property
    def invisible_fields(self):
        return self._fields.keys() - SAP_PRODUCT_TEMPLATE_FIELDS

    @property
    def readonly_fields(self):
        return self._fields.keys() - {'list_price'}

    @api.model
    def _dat_get_or_create_variant_from_template(self, template):
        if not template:
            return self.env['product.product']

        template = template.with_context(active_test=False)
        product = template.product_variant_id or template.product_variant_ids[:1]
        if product:
            return product

        template._create_variant_ids()
        template.invalidate_recordset(['product_variant_ids', 'product_variant_id'])
        product = template.product_variant_id or template.product_variant_ids[:1]
        if product:
            return product

        return template._create_first_product_variant()

    @api.model
    def _dat_sync_missing_variants_for_serial_popup(self):
        ctx = self.env.context
        if ctx.get('skip_dat_sync_missing_variants'):
            return
        if not (ctx.get('dat_create_missing_variant_on_search') or ctx.get('default_tracking') == 'lot'):
            return
        self.env['product.template'].with_context(
            skip_dat_sync_missing_variants=True,
        ).dat_create_missing_product_variants()

    @api.model
    def search_count(self, domain, limit=None):
        self._dat_sync_missing_variants_for_serial_popup()
        return super().search_count(domain, limit=limit)

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        self._dat_sync_missing_variants_for_serial_popup()
        return super().web_search_read(
            domain,
            specification,
            offset=offset,
            limit=limit,
            order=order,
            count_limit=count_limit,
        )

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        self._dat_sync_missing_variants_for_serial_popup()
        product_ids = list(super()._name_search(name, domain, operator, limit, order))
        domain = domain or []
        if not name or (limit and len(product_ids) >= limit):
            return product_ids

        positive_operators = ['=', 'ilike', '=ilike', 'like', '=like']
        if operator not in positive_operators:
            return product_ids

        remaining_limit = (limit - len(product_ids)) if limit else False
        exclude_domain = [('id', 'not in', product_ids)] if product_ids else []
        template_code_domains = [
            [('default_code', operator, name)],
            [('product_tmpl_id.default_code', operator, name)],
            [('name', operator, name)],
            [('product_tmpl_id.name', operator, name)],
            [('barcode', operator, name)],
            [('sap_model', operator, name)],
            [('sap_code_po', operator, name)],
            [('sap_serial_num', operator, name)],
            [('product_tmpl_id.sap_model', operator, name)],
            [('product_tmpl_id.sap_code_po', operator, name)],
            [('product_tmpl_id.sap_serial_num', operator, name)],
        ]
        if operator in ('=', '=ilike'):
            template_code_domains.append([('default_code', '=ilike', '%s%%' % name)])
            template_code_domains.append([('product_tmpl_id.default_code', '=ilike', '%s%%' % name)])
            template_code_domains.append([('sap_model', '=ilike', '%s%%' % name)])
            template_code_domains.append([('sap_code_po', '=ilike', '%s%%' % name)])
            template_code_domains.append([('sap_serial_num', '=ilike', '%s%%' % name)])

        for code_domain in template_code_domains:
            extra_ids = list(self._search(domain + exclude_domain + code_domain, limit=remaining_limit, order=order))
            product_ids.extend(extra_ids)
            if limit and len(product_ids) >= limit:
                break
            remaining_limit = (limit - len(product_ids)) if limit else False
            exclude_domain = [('id', 'not in', product_ids)] if product_ids else []
        if self.env.context.get('dat_create_missing_variant_on_search') and (not limit or len(product_ids) < limit):
            template_domain = [
                ('product_variant_ids', '=', False),
                ('type', 'in', ['consu', 'product']),
                '|', '|', '|',
                ('default_code', operator, name),
                ('name', operator, name),
                ('sap_model', operator, name),
                ('sap_code_po', operator, name),
            ]
            templates = self.env['product.template'].search(template_domain, limit=remaining_limit or None)
            for template in templates:
                product = self._dat_get_or_create_variant_from_template(template)
                if product and product.id not in product_ids:
                    product_ids.append(product.id)
                    if limit and len(product_ids) >= limit:
                        break
        return product_ids

