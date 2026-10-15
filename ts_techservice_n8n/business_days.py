from datetime import timedelta


def add_business_days(value, days=3, holidays=()):
    """Preserve local time, counting Monday-Friday after the sending day."""
    excluded = set(holidays)
    while days > 0:
        value += timedelta(days=1)
        if value.weekday() < 5 and value.date() not in excluded:
            days -= 1
    return value
