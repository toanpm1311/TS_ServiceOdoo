from datetime import datetime, timedelta
import re
import pytz
from odoo import api, fields, models, _
from odoo.addons.dat_base.tools.datetime import convert_datetime_str_to_object, format_datetime_object

from odoo.exceptions import UserError


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'abstract.sync.sap']

    @property
    def api_route(self):
        return '/BusinessPartners'

    @property
    def fields_mapping(self):
        """
        Provides the mapping between SAP Item API field names and Odoo fields.
        """
        return {
            'CardCode': 'card_code',
            'CardName': 'company_name',
            'Name': 'name',
            'GroupCode': 'sap_group_code',
            'GroupName': 'sap_group_name',
            'SlpName': 'sap_slp_name',
            'SlpCode': 'sap_slp_code',
            'U_BusinessUnit': 'sap_business_unit',
            'CntctCode': 'sap_cntct_code',
            'E_MailL': 'email',
            'Tel1': 'phone',
            'Tel2': 'mobile',
            'Cellolar': 'sap_cellolar',
            'UpdateDate': 'sap_update_date',
            'DefaultShipToCode': 'sap_ship_to_code',
            'DefaultShipToAddress': 'sap_ship_to_address',
            'DefaultBillToCode': 'sap_bill_to_code',
            'DefaultBillToAddress': 'sap_bill_to_address',
        }

    @property
    def identify_fields(self):
        return {'card_code', 'name'}

    @property
    def period_cron_xml_id(self):
        return 'dat_sync_sap.ir_cron_sync_sap_res_partner'

    def prepare_odoo_values(self, sap_values_list: list[dict]):
        """
        Prepares Odoo values for create and update from SAP data.
        Overrides to set is_sap_data=True for records synced from SAP (both create and update).
        """
        values_create, values_update = super().prepare_odoo_values(sap_values_list)
        # Set is_sap_data=True for both new and existing records synced from SAP
        for odoo_values in values_create + values_update:
            odoo_values['is_sap_data'] = True
        return values_create, values_update

    @api.model
    def sync_sap_data(self, start_dt: datetime = None, end_dt: datetime = None):
        """
        Fetches and synchronizes data from SAP for a specific time period.

        Subclasses can override this method to implement the specific logic
        for their corresponding SAP API endpoint and data model. This includes:
        1. Constructing the appropriate API request to SAP, likely using
           `start_dt` and `end_dt` as filter parameters.
        2. Handling the API response.
        3. Preparing the Odoo values using `prepare_odoo_values`.
        4. Creating or updating Odoo records using `create_odoo_records` and
           `update_odoo_records`.

        The base implementation here is a placeholder and does not perform any
        actual synchronization.

        :param start_dt: The start datetime of the period for which to sync data.
                         This should be a timezone-aware datetime object (UTC).
        :type start_dt: datetime.datetime
        :param end_dt: The end datetime of the period for which to sync data.
                       This should be a timezone-aware datetime object (UTC).
        :type end_dt: datetime.datetime
        """
        try:
            self.sync_customer_data(is_customer=False, start_dt=start_dt, end_dt=end_dt)
            self.sync_customer_data(is_customer=True, start_dt=start_dt, end_dt=end_dt)
        except UserError as err:
            raise UserError(str(err))

    def sync_customer_data(self, is_customer: bool, start_dt: datetime, end_dt: datetime):
        def format_dt(dt):
            return format_datetime_object(
                dt_object=dt,
                tz_from=pytz.utc,
                tz_to=self.source_timezone,
                format_to=self.sap_request_datetime_format
            ) if dt else ''

        json_vendor_data = {
            "IsCustomer": is_customer,
            "ModifiedDateStart": format_dt(start_dt),
            "ModifiedDateEnd": format_dt(end_dt)
        }

        sap_vendor_result = self.get_result(json=json_vendor_data)
        self._sync_sap_data(sap_vendor_result)

    @api.model
    def action_sync_sap_customer_data(self):
        self.sync_customer_data(
            is_customer=True,
            start_dt=None,
            end_dt=None,
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('SAP'),
                'message': _('Customer data synchronization completed.'),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'soft_reload',
                },
            },
        }

    def clean_odoo_field_value(self, fname: str, value):
        value = super().clean_odoo_field_value(fname, value)
        value_normalized = value.strip().lower() if isinstance(value, str) else value
        if fname == 'name' and (not value or value_normalized in ('tạm ẩn trong giai đoạn dev', 'null')):
            # SAP Customer/Vendor can have not name
            value = ''
        if fname in ('phone', 'mobile', 'sap_cellolar') and (
                not value or value_normalized in ('tạm ẩn trong giai đoạn dev', 'null', '00000')):
            value = ''
        return value

    @staticmethod
    def _set_primary_phone_from_sap(vals, existing_phone=False):
        if vals.get('phone'):
            return
        fallback_phone = vals.get('mobile') or vals.get('sap_cellolar')
        if fallback_phone:
            vals['phone'] = fallback_phone
        elif existing_phone:
            vals.pop('phone', None)

    @api.model
    def _sync_sap_data_for_period(self, start_dt: datetime, end_dt: datetime):
        """
        Overwrite of the abstract method.
        - Check if updateDate in range start and end. Continue if out of range.

        """
        self.sync_sap_data(start_dt, end_dt)

    @api.model
    def create(self, vals):
        card_code = str(vals.get('card_code') or '')
        name = vals.get('name', '')
        company_name = vals.get('company_name', '')
        if card_code.startswith('V'):
            vals['supplier_rank'] = 1
        if card_code.startswith('C'):
            vals['customer_rank'] = 1
        if company_name and not name:
            vals['name'] = company_name
        self._set_primary_phone_from_sap(vals)
        records = super().create(vals)
        records._compute_sale_person()
        return records

    def write(self, vals):
        code = str(vals.get('card_code') or '')
        if len(self) > 1:
            name = vals.get('name', '')
        else:
            name = vals.get('name', self.name)
        company_name = vals.get('company_name', '')
        if code.startswith('V'):
            vals['supplier_rank'] = 1
        if code.startswith('C'):
            vals['customer_rank'] = 1
        if company_name and not name:
            vals['name'] = company_name
        self._set_primary_phone_from_sap(vals, existing_phone=bool(self[:1].phone))
        res = super().write(vals)
        if 'sap_slp_code' in vals:
            self._compute_sale_person()
        return res
    
    @api.model
    def update_is_sap_data(self):
        """
        Cron job method to update is_sap_data=True for partners with sap_slp_code value.
        Runs periodically to ensure sync integrity.
        """
        partners = self.search([('sap_slp_code', '!=', False), ('sap_slp_code', '!=', '')])
        if partners:
            partners.write({'is_sap_data': True})
