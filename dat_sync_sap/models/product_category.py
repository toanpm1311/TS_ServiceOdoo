from datetime import datetime

from odoo import api, models


class ProductCategory(models.Model):
    _name = 'product.category'
    _inherit = ['product.category', 'abstract.sync.sap']

    @property
    def api_route(self):
        return '/ItemGroup'

    @property
    def fields_mapping(self):
        """
        Provides the mapping between SAP ItemGroup API field names and Odoo fields.
        """
        return {
            'ItmsGrpNam': 'name',
            'ItmsGrpCod': 'sap_code',
            'U_ProductLine': 'sap_product_line',
            'U_ProductFamily': 'sap_product_family',
            'U_Brand': 'sap_brand',
            'U_BusinessUnit': 'sap_business_unit',
        }

    @property
    def identify_fields(self):
        return {'sap_code'}

    @property
    def period_cron_xml_id(self):
        return 'dat_sync_sap.ir_cron_sync_sap_product_group'

    @api.model
    def _sync_sap_data_for_period(self, start_dt: datetime, end_dt: datetime):
        """
        Overwrite of the abstract method.
        - Changes: Sync all data instead of sync for period.
        """
        self.sync_sap_data()
