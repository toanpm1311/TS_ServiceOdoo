import logging
from datetime import datetime, timedelta

import pytz
import requests
from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AbstractSyncZalo(models.AbstractModel):
    """
    Abstract base class for synchronizing Zalo data into Odoo models.
    """
    _name = 'abstract.sync.zalo'
    _description = 'Abstract Model for Synchronization from Zalo'

    @property
    def source_timezone(self):
        return pytz.timezone('Asia/Ho_Chi_Minh')

    @property
    def zns_config(self):
        return self.env['zalo.zns.config'].get_config()

    @property
    def api_base_url(self):
        return self.zns_config.api_base_url if self.zns_config else ''

    @property
    def api_route(self):
        """
        The specific API route (path segment) for this model's Zalo endpoint.

        Concrete models inheriting from this abstract class **must** override
        this property to return the correct relative path for the specific
        ZALO API endpoint they interact with (e.g., '/message/template/', '/rating/').

        This route is intended to be combined with the base `api_base_url`
        (retrieved from system parameters) to form the complete URL for API calls
        related to this specific model.

        Defaults to '/', which is unlikely to be a functional endpoint and
        serves as a placeholder requiring implementation in subclasses.

        :return: The relative API path for the model-specific ZALO endpoint.
        :rtype: str
        """
        return '/'

    @property
    def api_headers(self):
        token_expires_at = self.zns_config.access_token_expires_at
        if not token_expires_at or token_expires_at < datetime.now():
            self.zns_config.oauth()
        return {
            'Content-Type': 'application/json',
            "access_token": self.zns_config.access_token,
        }

    @property
    def api_method(self):
        """
        The HTTP method to use for API requests.
        """
        return requests.get

    @property
    def fields_mapping(self):
        """
        Defines the mapping between ZALO API field names and Odoo model fields.

        This property serves as a template and **must be overridden** by concrete
        models inheriting from `AbstractSyncZalo`. The overriding implementation
        should return a dictionary where:
            - Keys are the field names as received from the specific ZALO API
              endpoint (defined by the model's `api_route`).
            - Values are the corresponding technical names of the fields within
              this Odoo model.

        This mapping is crucial for the `_sync_zalo_data` method to correctly
        translate and process the data fetched from the ZALO API into Odoo
        record values.

        Returns an empty dictionary by default in the abstract class, indicating
        that a concrete mapping is required in subclasses.

        :return: A dictionary defining the ZALO-to-Odoo field mapping.
        :rtype: dict
        """
        return {}

    @property
    def identify_fields(self):
        return {}

    @property
    def batch_size(self):
        batch_size = self.env['ir.config_parameter'].sudo(
        ).get_param('dat_sync_zalo.batch_size')
        return int(batch_size) if batch_size and batch_size.isdigit() else 100

    @property
    def period_cron_xml_id(self):
        """
        Specifies the XML ID of the ``ir.cron`` record for periodic data synchronization.
        """
        return ''

    def get_result(self, params=None, data=None, json=None, **kwargs) -> list:
        """
        :param params: (optional) Dictionary, list of tuples or bytes to send
        :param data: (optional) Dictionary, list of tuples, bytes, or file-like
            object to send in the body of the :class:`Request`.
        :param json: (optional) A JSON serializable Python object to send in the body of the :class:`Request`.
        :param **kwargs: Optional arguments that ``request`` takes.

        :return: list[dict]
        :rtype: list
        """
        response = self.api_method(
            self.api_base_url + self.api_route,
            headers=self.api_headers,
            params=params,
            data=data,
            json=json,
            **kwargs)
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('error') == 0:
                zalo_result = response_data.get('data').get('data')
                return zalo_result
            elif response_data.get('error') == -124:
                self.get_result(params, data, json, **kwargs)
        else:
            raise UserError(_("Failed to get ZALO data: %s") % response.reason)

    def check_allow_create(self, values: dict):
        """
        Performs pre-creation validation or filtering for a potential Odoo record.

        This method is called by `prepare_odoo_values` for each
        individual record's data *after* it has been mapped from ZALO fields
        to Odoo fields and cleaned, but *before* it's added to the list
        of records to be created via `create`.

        Subclasses should override this method to implement specific business
        rules or checks. For example, it can be used to prevent the creation
        of duplicate records based on certain keys (like checking `default_code`
        in the `product.template` override) or to skip records that
        don't meet specific criteria based on the incoming `values`.

        :param values: A dictionary containing the proposed Odoo field values
                       derived from a single ZALO record. Keys are Odoo field
                       names, values are the corresponding data.
        :type values: dict
        :return: `True` if the record represented by `values` should be
                 created, `False` to skip its creation.
        :rtype: bool
        """
        if None in {values.get(fname) for fname in self.identify_fields}:
            return False
        if self.search(self.search_domain_exists(values)).exists():
            return False
        return True

    def create_odoo_records(self, odoo_values_list):
        if self.batch_size:
            # Create records in batches
            res = self
            for i in range(0, len(odoo_values_list), self.batch_size):
                res += self.create(odoo_values_list[i:i + self.batch_size])
                self.env.cr.commit()
            return res
        else:
            return self.create(odoo_values_list)

    def search_domain_exists(self, record_values: dict):
        return [(fname, '=', record_values[fname]) for fname in self.identify_fields]

    def clean_odoo_field_value(self, fname: str, value):
        return value

    def prepare_odoo_values(self, zalo_values_list: list[dict]):
        values_create = []
        for zalo_values in zalo_values_list:
            odoo_values = {}
            for zalo_field, value in zalo_values.items():
                if zalo_field not in self.fields_mapping:
                    continue
                odoo_field = self.fields_mapping[zalo_field]
                value_cleaned = self.clean_odoo_field_value(odoo_field, value)
                odoo_values[odoo_field] = value_cleaned
            if self.check_allow_create(odoo_values):
                values_create.append(odoo_values)

        return values_create

    @api.model
    def prepare_params_for_period_sync_zalo(self, start_dt: datetime, end_dt: datetime):
        json_data = {}
        if start_dt:
            start_dt_local = self.source_timezone.localize(start_dt)
            start_dt = start_dt_local.astimezone(pytz.utc)
            json_data['from_time'] = int(start_dt.timestamp() * 1000)
        if end_dt:
            end_dt_local = self.source_timezone.localize(end_dt)
            end_dt = end_dt_local.astimezone(pytz.utc)
            json_data['to_time'] = int(end_dt.timestamp() * 1000)
        return json_data

    @api.model
    def _sync_zalo_data_for_period(self, start_dt: datetime, end_dt: datetime):
        """
        Fetches and synchronizes data from ZALO for a specific time period.

        Subclasses can override this method to implement the specific logic
        for their corresponding ZALO API endpoint and data model. This includes:
        1. Constructing the appropriate API request to ZALO, likely using
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
        params = self.prepare_params_for_period_sync_zalo(start_dt, end_dt)
        zalo_result = self.get_result(params=params)
        self._sync_zalo_data(zalo_result)

    @api.model
    def sync_zalo_data_for_period(self):
        """
        Updates Odoo data with ZALO data for a specific time period.
        This function is typically run automatically by a scheduled task.

        It uses the `period_cron_xml_id` property to find the relevant scheduled task.
        Based on this task's last successful run, it determines the correct
        period (start and end times) for fetching new data.

        It then calls the `_sync_zalo_data_for_period` method, which handles
        the actual fetching of data from ZALO for that period and updates
        the records in Odoo.

        If the synchronization is successful, this function updates the
        scheduled task's `lastcall_success` time to the end of the current period.
        It also updates the status of the latest run (trigger) for that task to 'done'.

        If an error occurs during the process, the function will catch it,
        and an error message will be recorded.
        """
        self = self.sudo()
        status = 'failed'
        try:
            cron = self.env.ref(self.period_cron_xml_id)
            if not cron:
                return

            start_dt, end_dt = cron.lastcall_success, cron.nextcall
            if start_dt:
                start_dt = start_dt - timedelta(hours=1)  # buffer 1h
            self._sync_zalo_data_for_period(start_dt, end_dt)
            status = 'done'
        except Exception as e:
            _logger.warning(str(e))

        if status == 'done':
            cron.lastcall_success = end_dt
        self.env.cr.commit()

    @api.model
    def _sync_zalo_data(self, zalo_vals_list: list):
        values_create = self.prepare_odoo_values(zalo_vals_list)
        if values_create:
            self.create_odoo_records(values_create)
