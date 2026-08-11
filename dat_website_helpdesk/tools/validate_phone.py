import re


def is_valid_phone_number(phone):
    if not isinstance(phone, str) or not phone.strip():
        return False
    pattern = r'^(?:\+|0)(?:\d[ -.]?){8,14}\d$'
    return bool(re.match(pattern, phone.strip()))
