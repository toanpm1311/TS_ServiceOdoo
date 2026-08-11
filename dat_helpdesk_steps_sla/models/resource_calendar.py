from odoo import models, _
from odoo.addons.resource.models.utils import Intervals, float_to_time, make_aware, datetime_to_string, string_to_datetime



class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    def get_work_duration_data_with_resource(self, from_datetime, to_datetime, compute_leaves=True, domain=None, resource=None):
        if resource and compute_leaves:
            from_datetime, dummy = make_aware(from_datetime)
            to_datetime, dummy = make_aware(to_datetime)

            intervals = self._work_intervals_batch(from_datetime, to_datetime, domain=domain, resources=resource)[resource.id]

            return self._get_attendance_intervals_days_data(intervals)
        else:
            return  self.get_work_duration_data(from_datetime, to_datetime, compute_leaves=compute_leaves, domain=domain)
        