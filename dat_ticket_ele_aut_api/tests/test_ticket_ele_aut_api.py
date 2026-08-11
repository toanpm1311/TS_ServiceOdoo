from datetime import date, datetime, timedelta, timezone

from odoo.tests.common import TransactionCase


class TestTicketEleAutApi(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ticket_model = cls.env['ticket.helpdesk']

    def test_json_safe_dates_are_iso_8601(self):
        self.assertEqual(
            self.ticket_model._ele_aut_api_json_safe(date(2026, 7, 24)),
            '2026-07-24',
        )
        self.assertEqual(
            self.ticket_model._ele_aut_api_json_safe(
                datetime(2026, 7, 24, 3, 30, tzinfo=timezone.utc),
            ),
            '2026-07-24T03:30:00+00:00',
        )

    def test_only_ele_and_aut_are_accepted(self):
        domain = self.ticket_model.ele_aut_api_business_area_domain([
            'ELE',
            'AUT',
            'SOL',
        ])
        self.assertIn(
            ('saleperson_id.sap_business_area', '=ilike', 'ELE'),
            domain,
        )
        self.assertIn(
            ('saleperson_id.sap_business_area', '=ilike', 'AUT'),
            domain,
        )
        self.assertNotIn(
            ('saleperson_id.sap_business_area', '=ilike', 'SOL'),
            domain,
        )

    def test_sol_only_returns_empty_domain(self):
        domain = self.ticket_model.ele_aut_api_business_area_domain(['SOL'])
        self.assertEqual(domain, [('id', '=', 0)])

    def test_sync_cursor_round_trip(self):
        snapshot_at = datetime(2026, 8, 4, 13, 0)
        last_updated_at = datetime(2026, 8, 3, 9, 15, 30)
        cursor = self.ticket_model._ele_aut_api_encode_cursor(
            snapshot_at,
            last_updated_at,
            42,
        )

        self.assertEqual(
            self.ticket_model._ele_aut_api_decode_cursor(cursor),
            (snapshot_at, last_updated_at, 42),
        )

    def test_invalid_sync_cursor_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Invalid pagination cursor'):
            self.ticket_model._ele_aut_api_decode_cursor('not-a-cursor')

    def test_datetime_is_normalized_to_naive_utc(self):
        value = datetime(
            2026,
            8,
            4,
            20,
            0,
            0,
            123456,
            tzinfo=timezone(timedelta(hours=7)),
        )
        self.assertEqual(
            self.ticket_model._ele_aut_api_normalize_datetime(value),
            datetime(2026, 8, 4, 13, 0),
        )
