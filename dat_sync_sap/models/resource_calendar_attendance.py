from datetime import datetime

from odoo import api, models


class ResourceCalendarAttendance(models.Model):
    _name = 'resource.calendar.attendance'
    _inherit = ['resource.calendar.attendance', 'abstract.sync.sap']

    @property
    def api_route(self):
        return '/WorkingTimes'

    @property
    def fields_mapping(self):
        """
        Provides the mapping between SAP WorkingTimes API field names and Odoo fields.
        """
        return {
            'MorningWorkStarHours': 'hour_from',
            'MorningWorkEndHours': 'hour_to',
            'AfternoonWorkStarHours': 'hour_from',
            'AfternoonWorkEndHours': 'hour_to',
            'DayOfWeek': 'dayofweek',
        }

    @property
    def identify_fields(self):
        return {'dayofweek', 'day_period', 'calendar_id'}

    @property
    def period_cron_xml_id(self):
        return 'dat_sync_sap.ir_cron_sync_sap_working_time'

    def clean_odoo_field_value(self, fname: str, value):
        value = super().clean_odoo_field_value(fname, value)
        if fname == 'dayofweek':
            value = self.get_selection_key_from_value(fname, value)
        if fname in ['hour_from', 'hour_to']:
            time_obj = datetime.strptime(value, "%H:%M:%S").time()
            hour = time_obj.hour
            minute = time_obj.minute
            second = time_obj.second
            value = hour + minute / 60 + second / 3600
        return value

    def prepare_odoo_values_by_day_period(self, day_period: str, sap_values, default_values={}):
        for sap_field, value in sap_values.items():
            if sap_field not in self.fields_mapping or day_period not in sap_field.lower():
                continue
            odoo_field = self.fields_mapping[sap_field]
            value_cleaned = self.clean_odoo_field_value(odoo_field, value)
            default_values[odoo_field] = value_cleaned
        default_values['day_period'] = day_period
        return default_values

    def prepare_odoo_values(self, sap_values_list: list[dict]):
        values_create = []
        values_update = []
        calendar_id = self.env.ref('resource.resource_calendar_std')
        if not calendar_id:
            calendar_id = self.env['resource.calendar'].create({
                'name': 'DAT Standard Calendar',
                'tz': self.source_timezone.zone,
            })
        else:
            calendar_id.tz = self.source_timezone.zone

        for sap_values in sap_values_list:
            dayofweek_label = sap_values.pop('DayOfWeek')
            if not dayofweek_label:
                continue
            dayofweek = self.clean_odoo_field_value(
                'dayofweek', dayofweek_label)
            default_odoo_values = {
                'dayofweek': dayofweek,
                'calendar_id': calendar_id.id,
            }
            morning_odoo_values = self.prepare_odoo_values_by_day_period(
                'morning',
                sap_values,
                default_values={**default_odoo_values, 'name': f'{dayofweek_label} Morning'})
            if morning_odoo_values:
                if self.check_allow_create(morning_odoo_values):
                    values_create.append(morning_odoo_values)
                elif self.check_allow_update(morning_odoo_values):
                    values_update.append(morning_odoo_values)
            afternoon_odoo_values = self.prepare_odoo_values_by_day_period(
                'afternoon',
                sap_values,
                default_values={**default_odoo_values, 'name': f'{dayofweek_label} Afternoon'})
            if afternoon_odoo_values:
                if self.check_allow_create(afternoon_odoo_values):
                    values_create.append(afternoon_odoo_values)
                elif self.check_allow_update(afternoon_odoo_values):
                    values_update.append(afternoon_odoo_values)
        return values_create, values_update

    @api.model
    def _sync_sap_data_for_period(self, start_dt: datetime, end_dt: datetime):
        """
        Overwrite of the abstract method.
        - Changes: Sync all data instead of sync for period.
        """
        self.sync_sap_data()
