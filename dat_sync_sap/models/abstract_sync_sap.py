from datetime import datetime, timedelta

import pytz
import requests
from odoo import _, api, fields, models
from odoo.addons.dat_sap_config.tools.datetime import (
    convert_datetime_str_to_object,
    format_datetime_object,
)
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class AbstractSyncSAP(models.AbstractModel):
    """
    Abstract base class for synchronizing Odoo models with an external SAP system.

    This class provides a common framework and reusable logic for integrations,
    handling aspects like API communication, data mapping, transformation,
    and record management within Odoo. It aims to simplify the development
    of specific synchronization tasks by abstracting away boilerplate code.

    Key Responsibilities and Features:
    - Abstraction Layer: Offers a standardized interface for model-specific sync logic.
    - SAP API Interaction: Manages connection details, authentication (bearer tokens),
      and provides a generic method for making API calls.
    - Data Mapping: Requires subclasses to define `fields_mapping` for translating
      SAP field names to Odoo field names.
    - Data Transformation: Includes `clean_odoo_field_value` for basic type conversions
      (e.g., booleans, datetimes with timezone handling).
    - Record Identification: Uses `identify_fields` (defined in subclasses) for
      uniquely identifying records for create/update operations.
    - Create/Update Logic: Provides `check_allow_create` and `check_allow_update`
      hooks for custom validation before creating or updating Odoo records.
      Supports batch creation of records.
    - Synchronization Strategies:
        - `sync_sap_data()`: For full, manual synchronization.
        - `sync_sap_data_for_period()`: For periodic, cron-driven synchronization,
          fetching data modified within a specific time window.
    - Error Handling: Updates `ir.cron.trigger` status and error messages for
      periodic syncs.
    - Configuration: Relies on Odoo system parameters for SAP connection details,
      batch sizes, and uses defined datetime formats and source timezone for
      accurate data handling.

    Usage:
    Concrete models requiring SAP synchronization should inherit from this class
    and primarily override:
    - `api_route`: The specific SAP API endpoint path.
    - `fields_mapping`: The dictionary mapping SAP fields to Odoo fields.
    - `identify_fields`: A set of Odoo field names for unique record identification.
    - `period_cron_xml_id` (if periodic sync is used): The XML ID of the `ir.cron` job.

    Further customization can be achieved by overriding methods like
    `prepare_odoo_values`, `check_allow_create`, `check_allow_update`, etc.
    """

    _name = 'abstract.sync.sap'
    _description = 'Abstract Model for Synchronization with SAP'

    @property
    def source_timezone(self):
        return pytz.timezone('Asia/Ho_Chi_Minh')

    @property
    def api_url(self):
        return self.env['ir.config_parameter'].sudo().get_param('dat_sync_sap.sap_api_url')

    @property
    def api_route(self):
        """
        The specific API route (path segment) for this model's SAP endpoint.

        Concrete models inheriting from this abstract class **must** override
        this property to return the correct relative path for the specific
        SAP API endpoint they interact with (e.g., '/Items', '/BusinessPartners').

        This route is intended to be combined with the base `api_url`
        (retrieved from system parameters) to form the complete URL for API calls
        related to this specific model.

        Defaults to '/', which is unlikely to be a functional endpoint and
        serves as a placeholder requiring implementation in subclasses.

        :return: The relative API path for the model-specific SAP endpoint.
        :rtype: str
        """
        return '/'

    @property
    def api_headers(self):
        token = self.env['res.config.settings']._get_sap_token()
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
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
        Defines the mapping between SAP API field names and Odoo model fields.

        This property serves as a template and **must be overridden** by concrete
        models inheriting from `AbstractSyncSAP`. The overriding implementation
        should return a dictionary where:
            - Keys are the field names as received from the specific SAP API
              endpoint (defined by the model's `api_route`).
            - Values are the corresponding technical names of the fields within
              this Odoo model.

        This mapping is crucial for the `_sync_sap_data` method to correctly
        translate and process the data fetched from the SAP API into Odoo
        record values.

        Returns an empty dictionary by default in the abstract class, indicating
        that a concrete mapping is required in subclasses.

        :return: A dictionary defining the SAP-to-Odoo field mapping.
        :rtype: dict
        """
        return {}

    @property
    def identify_fields(self):
        return {}

    @property
    def batch_size(self):
        batch_size = self.env['ir.config_parameter'].sudo(
        ).get_param('dat_sync_sap.batch_size')
        return int(batch_size) if batch_size and batch_size.isdigit() else 100

    @property
    def sap_request_datetime_format(self):
        return '%Y-%m-%d %H:%M:%S.%f'

    @property
    def sap_response_datetime_format(self):
        return '%Y-%m-%dT%H:%M:%S'

    @property
    def period_cron_xml_id(self):
        """
        Specifies the XML ID of the ``ir.cron`` record for periodic data synchronization.
        """
        return ''

    def get_result(self, params=None, data=None, json=None, result_text=None, **kwargs) -> list:
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
            self.api_url + self.api_route,
            headers=self.api_headers,
            params=params,
            data=data,
            json=json,
            **kwargs)
        if response.status_code == 200:
            if not result_text:
                result_text = 'result'
            sap_result = response.json().get(result_text)
            return sap_result
        else:
            raise UserError(_("Failed to get SAP data: %s") % response.reason)

    def clean_odoo_field_value(self, fname: str, value):
        field = self._fields[fname]
        if isinstance(field, fields.Boolean) and value:
            if isinstance(value, str):
                value = value.lower() == 'y'
        elif isinstance(field, fields.Datetime) and value and not isinstance(value, datetime):
            datetime_object = convert_datetime_str_to_object(
                value,
                tz_to=pytz.utc,
                tz_from=self.source_timezone,
                format_from=self.sap_response_datetime_format)
            value = datetime_object.strftime(DEFAULT_SERVER_DATETIME_FORMAT) if datetime_object else False
        return value

    def check_allow_create(self, values: dict):
        """
        Performs pre-creation validation or filtering for a potential Odoo record.

        This method is called by `prepare_odoo_values` for each
        individual record's data *after* it has been mapped from SAP fields
        to Odoo fields and cleaned, but *before* it's added to the list
        of records to be created via `create`.

        Subclasses should override this method to implement specific business
        rules or checks. For example, it can be used to prevent the creation
        of duplicate records based on certain keys (like checking `default_code`
        in the `product.template` override) or to skip records that
        don't meet specific criteria based on the incoming `values`.

        :param values: A dictionary containing the proposed Odoo field values
                       derived from a single SAP record. Keys are Odoo field
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

    def check_allow_update(self, values: dict):
        """
        Performs pre-update validation or filtering for a potential Odoo record.

        This method is called by `prepare_odoo_values` for each
        individual record's data *after* it has been mapped from SAP fields
        to Odoo fields and cleaned, but *before* it's added to the list
        of records to be updated via `write`.

        Subclasses should override this method to implement specific business
        rules or checks.

        :param values: A dictionary containing the proposed Odoo field values
                       derived from a single SAP record. Keys are Odoo field
                       names, values are the corresponding data.
        :type values: dict
        :return: `True` if the record represented by `values` should be
                 updated, `False` to skip its update.
        :rtype: bool
        """
        if None in {values.get(fname) for fname in self.identify_fields}:
            return False
        if self.search(self.search_domain_exists(values)).exists():
            return True
        return False

    def get_selection_key_from_value(self, odoo_fname, value):
        selection = self._fields[odoo_fname].selection
        return next((k for k, v in selection if v == value), None)

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

    def update_odoo_records(self, odoo_values_list):
        res = False
        for values in odoo_values_list:
            record = self.search(self.search_domain_exists(values), limit=1)
            for fname in self.identify_fields:
                values.pop(fname, None)
            res = record.write(values)
        return res

    def prepare_odoo_values(self, sap_values_list: list[dict]):
        values_create = []
        values_update = []
        for sap_values in sap_values_list:
            odoo_values = {}
            for sap_field, value in sap_values.items():
                if sap_field not in self.fields_mapping:
                    continue
                odoo_field = self.fields_mapping[sap_field]
                value_cleaned = self.clean_odoo_field_value(odoo_field, value)
                odoo_values[odoo_field] = value_cleaned
            if self.check_allow_create(odoo_values):
                values_create.append(odoo_values)
            elif self.check_allow_update(odoo_values):
                values_update.append(odoo_values)
        return values_create, values_update

    def get_all_sap_records(self):
        return self.get_result()

    @api.model
    def _sync_sap_data_for_period(self, start_dt: datetime, end_dt: datetime):
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
        if start_dt:
            start_dt_str = format_datetime_object(
                dt_object=start_dt,
                tz_from=pytz.utc,
                tz_to=self.source_timezone,
                format_to=self.sap_request_datetime_format)
        else:
            start_dt_str = ''
        if end_dt:
            end_dt_str = format_datetime_object(
                dt_object=end_dt,
                tz_from=pytz.utc,
                tz_to=self.source_timezone,
                format_to=self.sap_request_datetime_format)
        else:
            end_dt_str = ''

        json_data = {
            "ModifiedDateStart": start_dt_str,
            "ModifiedDateEnd": end_dt_str
        }
        sap_result = self.get_result(json=json_data)
        self._sync_sap_data(sap_result)

    @api.model
    def _sync_sap_data(self, sap_result: list):
        values_create, values_update = self.prepare_odoo_values(sap_result)
        if values_create:
            self.create_odoo_records(values_create)
        if values_update:
            self.update_odoo_records(values_update)

    @api.model
    def sync_sap_data(self):
        """
        Query and sync all data of model. Used to sync manual.
        """
        self = self.sudo()
        sap_result = self.get_all_sap_records()
        self._sync_sap_data(sap_result)
        self.env.cr.commit()

    @api.model
    def sync_sap_data_for_period(self):
        """
        Updates Odoo data with SAP data for a specific time period.
        This function is typically run automatically by a scheduled task.

        It uses the `period_cron_xml_id` property to find the relevant scheduled task.
        Based on this task's last successful run, it determines the correct
        period (start and end times) for fetching new data.

        It then calls the `_sync_sap_data_for_period` method, which handles
        the actual fetching of data from SAP for that period and updates
        the records in Odoo.

        If the synchronization is successful, this function updates the
        scheduled task's `lastcall_success` time to the end of the current period.
        It also updates the status of the latest run (trigger) for that task to 'done'.

        If an error occurs during the process, the function will catch it,
        and an error message will be recorded.
        """
        self = self.sudo()
        # SAP crons share related records (for example employees and partner contacts).
        # Queue their write phase to avoid serialization failures when schedules overlap.
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            ('dat_sync_sap_periodic_sync',),
        )
        cron = self.env.ref(self.period_cron_xml_id)
        if not cron:
            return

        start_dt, end_dt = cron.lastcall_success, cron.nextcall
        if start_dt:
            start_dt = start_dt - timedelta(days=1)  # buffer 1d
        self._sync_sap_data_for_period(start_dt, end_dt)
        self.env.cr.commit()
