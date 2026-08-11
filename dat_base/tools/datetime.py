from datetime import datetime

import pytz
from odoo import _


def convert_datetime_str_to_object(date_string: str, tz_to: pytz.timezone, tz_from: pytz.timezone, format_from: str):
    try:
        dt = datetime.strptime(date_string, format_from)
        dt_local = tz_from.localize(dt)
        return dt_local.astimezone(tz_to)
    except ValueError:
        raise ValueError(_("Invalid datetime format"))


def format_datetime_object(dt_object: datetime, tz_to: pytz.timezone, tz_from: pytz.timezone, format_to: str):
    dt_local = tz_from.localize(dt_object)
    dt_local = dt_local.astimezone(tz_to)
    return dt_local.strftime(format_to)
