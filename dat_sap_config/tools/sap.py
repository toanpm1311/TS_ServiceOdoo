from datetime import date, datetime

import pytz
from bs4 import BeautifulSoup
from odoo.http import request

from .datetime import (
    format_date_object,
    format_datetime_object,
)


def get_sap_request_body_date(dt_object):
    SAP_DATE_FORMART = '%Y-%m-%d'
    user_tz = request.env.user.tz or 'Asia/Ho_Chi_Minh'

    if isinstance(dt_object, date):
        return format_date_object(dt_object, SAP_DATE_FORMART)
    elif isinstance(dt_object, datetime):
        return format_datetime_object(
            dt_object,
            tz_from=pytz.utc,
            tz_to=user_tz,
            format_to=SAP_DATE_FORMART)
    return ''


def get_sap_request_body_datetime(dt_object: datetime):
    SAP_DATETIME_FORMART = '%Y-%m-%dT%H:%M:%S'
    user_tz = request.env.user.tz or 'Asia/Ho_Chi_Minh'

    if isinstance(dt_object, datetime):
        return format_datetime_object(
            dt_object,
            tz_from=pytz.utc,
            tz_to=user_tz,
            format_to=SAP_DATETIME_FORMART)
    return ''


def get_sap_request_body_bool(value: bool):
    return 'Y' if value else 'N'


def get_html_plain_text(html):
    html_str = str(html)
    soup = BeautifulSoup(html_str, 'html.parser')
    return soup.get_text()


def get_sap_request_body_html(value):
    return get_html_plain_text(value)
