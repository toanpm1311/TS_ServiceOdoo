import importlib.util
import unittest
from datetime import date, datetime
from pathlib import Path

spec = importlib.util.spec_from_file_location('business_days', Path(__file__).parents[1] / 'business_days.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


class BusinessDayTests(unittest.TestCase):
    def test_monday_due_thursday_same_time(self):
        self.assertEqual(helpers.add_business_days(datetime(2026, 10, 12, 14, 30)), datetime(2026, 10, 15, 14, 30))

    def test_friday_skips_weekend(self):
        self.assertEqual(helpers.add_business_days(datetime(2026, 10, 16, 9)), datetime(2026, 10, 21, 9))

    def test_weekend_send_starts_counting_monday(self):
        self.assertEqual(helpers.add_business_days(datetime(2026, 10, 17, 9)), datetime(2026, 10, 21, 9))

    def test_holiday_excluded(self):
        self.assertEqual(helpers.add_business_days(datetime(2026, 10, 12, 9), holidays=[date(2026, 10, 13)]), datetime(2026, 10, 16, 9))

    def test_month_and_year_boundary(self):
        self.assertEqual(helpers.add_business_days(datetime(2026, 12, 31, 9), holidays=[date(2027, 1, 1)]), datetime(2027, 1, 6, 9))


if __name__ == '__main__':
    unittest.main()
