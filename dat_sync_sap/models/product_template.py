from odoo import api, models


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'abstract.sync.sap']

    @property
    def api_route(self):
        return '/Items'

    @property
    def fields_mapping(self):
        """
        Provides the mapping between SAP Item API field names and Odoo fields.
        """
        return {
            'ItemCode': 'default_code',
            'ItemName': 'name',
            'ItmsGrpCod': 'sap_group_code',
            'ItmsGrpNam': 'sap_group_name',
            'U_ProductLine': 'sap_product_line',
            'U_ProductFamily': 'sap_product_family',
            'U_Brand': 'sap_brand',
            'U_BusinessUnit': 'sap_business_unit',
            'ManSerNum': 'sap_man_ser_num',
            'ItemModel': 'sap_model',
            'ItemNote': 'description',
            'U_WMonth': 'sap_wmonth',
            'U_WMonth_Dist': 'sap_wmonth_dist',
            'U_ALE_Expiration': 'sap_ale_expiration',
            'InvntryUom': 'sap_uom',
            'BuyUnitMsr': 'sap_uom_po',
            'SalUnitMsr': 'sap_uom_so',
            'Quantity': 'qty_available',
            'HeThongGiaVon': 'sap_costing_system',
            'LeadTime': 'sale_delay',
            'ToleranDay': 'sap_toleran_day',
            'U_ItemCodePO': 'sap_code_po',
            'CreateDate': 'sap_create_date',
            'UpdateDate': 'sap_update_date',
        }

    @property
    def identify_fields(self):
        return {'default_code'}

    @property
    def period_cron_xml_id(self):
        return 'dat_sync_sap.ir_cron_sync_sap_product'

    def clean_odoo_field_value(self, fname: str, value):
        value = super().clean_odoo_field_value(fname, value)
        if fname == 'name' and not value:
            # SAP Items can have not name
            value = ' '
        return value

    def _ensure_product_variants(self):
        if self.env.context.get('skip_dat_ensure_product_variants'):
            return
        Product = self.env['product.product'].with_context(
            active_test=False,
            skip_dat_ensure_product_variants=True,
        )
        for template in self.with_context(active_test=False):
            if template.type not in ('consu', 'product'):
                continue
            product = Product._dat_get_or_create_variant_from_template(template)
            if product and not product.active:
                product.active = True

    def _find_existing_by_default_code(self, values):
        default_code = values.get('default_code')
        if not default_code:
            return self.browse()
        return self.with_context(active_test=False).search([
            ('default_code', '=', default_code),
        ], order='active desc, write_date desc, id desc', limit=1)

    def check_allow_create(self, values):
        if not values.get('default_code'):
            return False
        return not bool(self._find_existing_by_default_code(values))

    def check_allow_update(self, values):
        if not values.get('default_code'):
            return False
        return bool(self._find_existing_by_default_code(values))

    def prepare_odoo_values(self, sap_values_list):
        values_create, values_update = super().prepare_odoo_values(sap_values_list)

        dedup_create = {}
        for values in values_create:
            dedup_create[values.get('default_code')] = values

        dedup_update = {}
        for values in values_update:
            dedup_update[values.get('default_code')] = values

        return list(dedup_create.values()), list(dedup_update.values())

    def update_odoo_records(self, odoo_values_list):
        res = False
        for values in odoo_values_list:
            record = self._find_existing_by_default_code(values)
            if not record:
                continue
            vals = dict(values)
            vals.pop('default_code', None)
            if not record.active:
                vals['active'] = True
            res = record.write(vals)
        return res

    @api.model
    def create(self, vals):
        records = super().create(vals)
        # Explicitly call the compute method to set the 'tracking' field
        records._compute_tracking()
        records._compute_uom_id()
        records._compute_uom_po_id()
        records._compute_uom_so_id()
        records._compute_categ_id()
        records._compute_business_unit()
        records._ensure_product_variants()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'sap_uom' in vals:
            self._compute_uom_id()
        if 'sap_uom_po' in vals:
            self._compute_uom_po_id()
        if 'sap_uom_so' in vals:
            self._compute_uom_so_id()
        if 'sap_group_code' in vals:
            self._compute_categ_id()
        if 'sap_business_unit' in vals:
            self._compute_categ_id()
        if self.env.context.get('create_product_product') is not False:
            self._ensure_product_variants()
        return res

    @api.model
    def sync_sap_data(self):
        self.env['uom.uom'].sync_sap_data()
        super().sync_sap_data()

    @api.model
    def sync_sap_data_for_period(self):
        self.env['uom.uom'].sync_sap_data()
        super().sync_sap_data_for_period()
