from datetime import date, datetime

import pytz
from odoo import _


def convert_datetime_str_to_object(date_string: str, tz_to: pytz.timezone, tz_from: pytz.timezone, format_from: str):
    try:
        # Add zeros to the microseconds part if less than 6 digits
        if '.' in date_string:
            main_part, ms = date_string.split('.')
            ms = (ms + '000000')[:6]  # pad to 6 digits
            date_string = main_part + '.' + ms
            dt = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S.%f')
        else:
            dt = datetime.strptime(date_string, format_from)
        if dt == datetime.min or dt.year <= 1:
            return False
        dt_local = tz_from.localize(dt)
        return dt_local.astimezone(tz_to)
    except ValueError:
        raise ValueError(_("Invalid datetime format"))


def format_date_object(dt_object: date, format_to: str):
    return dt_object.strftime(format_to)


def format_datetime_object(dt_object: datetime, tz_to: pytz.timezone, tz_from: pytz.timezone, format_to: str):
    dt_local = tz_from.localize(dt_object)
    dt_local = dt_local.astimezone(tz_to)
    return dt_local.strftime(format_to)
