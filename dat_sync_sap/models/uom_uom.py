from datetime import datetime

from odoo import api, models


class UoM(models.Model):
    _name = 'uom.uom'
    _inherit = ['uom.uom', 'abstract.sync.sap']

    @property
    def api_route(self):
        return '/ItemUnit'

    @property
    def fields_mapping(self):
        """
        Provides the mapping between SAP Item API field names and Odoo fields.
        """
        return {
            'Name': 'name',
            'CategoryId': 'category_id',
            'UomType': 'uom_type'
        }

    @property
    def identify_fields(self):
        return {'category_id', 'name'}

    def search_domain_exists(self, record_values: dict):
        return [('category_id', '=', record_values['category_id']), ('name', '=ilike', record_values['name'])]

    def check_allow_update(self, values: dict):
        return False

    def prepare_odoo_values(self, sap_values_list: list):
        category_unit = self.env.ref('uom.product_uom_categ_unit')
        if not category_unit:
            return [], []
        sap_values_list = [
            {
                'Name': value,
                'CategoryId': category_unit.id,
                'UomType': 'bigger'
            } for value in sap_values_list
        ]
        return super().prepare_odoo_values(sap_values_list)

    @api.model
    def _sync_sap_data_for_period(self, start_dt: datetime, end_dt: datetime):
        """
        Overwrite of the abstract method.
        - Changes: Sync all data instead of sync for period.
        """
        self.sync_sap_data()
