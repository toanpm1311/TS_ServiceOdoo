import runpy
import unittest
from pathlib import Path


recovery = runpy.run_path(str(Path(__file__).with_name('restore_so_prices.py')))
confirmed_payloads = recovery['confirmed_payloads']
original_prices = recovery['original_prices']


class RecoveryEvidenceTests(unittest.TestCase):
    def _request(self, message_id=1, side='main', price=500000):
        import html
        import json
        route = '/CreateSOForWarrFix' + ('_LT' if side == 'lt' else '')
        data = {'route': route, 'payload': {'Lines': [
            {'ItemCode': 'PART-A', 'Price': price / 2, 'U_OrigiPrice': price},
        ]}}
        return {'id': message_id, 'body': '<b>SAP REQUEST PAYLOAD - %s</b><pre>%s</pre>'
                % (route, html.escape(json.dumps(data)))}

    def _success(self, message_id=2, side='main', doc='SO-1'):
        return {'id': message_id, 'body': '<p>%s SO created in SAP: %s</p>'
                % ('Main' if side == 'main' else 'LT', doc)}

    def test_request_without_success_is_not_evidence(self):
        self.assertEqual(confirmed_payloads([self._request()], {'main': 'SO-1'}), [])

    def test_only_matching_saved_document_is_accepted(self):
        messages = [self._request(), self._success(doc='SO-OTHER')]
        self.assertEqual(confirmed_payloads(messages, {'main': 'SO-1'}), [])

    def test_html_payload_uses_original_price_not_discounted_price(self):
        result = confirmed_payloads([self._request(), self._success()], {'main': 'SO-1'})
        self.assertEqual(result[0][0], 1)
        self.assertEqual(original_prices(result[0][1], 'PART-A'), {500000.0})

    def test_failed_later_request_does_not_replace_successful_evidence(self):
        messages = [self._request(), self._success(), self._request(3, price=1)]
        result = confirmed_payloads(messages, {'main': 'SO-1'})
        self.assertEqual(original_prices(result[0][1], 'PART-A'), {500000.0})

    def test_main_and_lt_have_independent_success_notes(self):
        messages = [self._request(), self._request(2, side='lt'),
                    self._success(3, side='lt', doc='LT-1'), self._success(4)]
        result = confirmed_payloads(messages, {'main': 'SO-1', 'lt': 'LT-1'})
        self.assertEqual({item[0] for item in result}, {1, 2})

    def test_unrelated_batch_side_is_not_used(self):
        messages = [self._request(side='lt'), self._success(side='lt', doc='LT-OTHER')]
        self.assertEqual(confirmed_payloads(messages, {'main': 'SO-1'}), [])

    def test_duplicate_codes_with_different_prices_remain_ambiguous(self):
        payload = {'Lines': [{'ItemCode': 'FEE', 'U_OrigiPrice': price}
                             for price in (0, 1, 0)]}
        self.assertEqual(original_prices(payload, 'FEE'), {0.0, 1.0})

    def test_identical_batch_prices_are_unambiguous(self):
        payload = {'Lines': [{'ItemCode': 'PART', 'U_OrigiPrice': 500000}] * 3}
        self.assertEqual(original_prices(payload, 'PART'), {500000.0})

    def test_free_item_can_be_restored_to_zero(self):
        self.assertEqual(original_prices({'Lines': [
            {'ItemCode': 'FREE', 'U_OrigiPrice': 0},
        ]}, 'FREE'), {0.0})

    def test_missing_original_price_is_rejected(self):
        with self.assertRaises(ValueError):
            original_prices({'Lines': [{'ItemCode': 'PART', 'Price': 500000}]}, 'PART')

    def test_invalid_prices_are_rejected(self):
        for price in ('NaN', 'Infinity', -1, True):
            with self.subTest(price=price), self.assertRaises(ValueError):
                original_prices({'Lines': [{'ItemCode': 'PART', 'U_OrigiPrice': price}]}, 'PART')

    def test_broken_request_cannot_reuse_an_earlier_pending_request(self):
        messages = [self._request(), {'id': 2, 'body': 'SAP REQUEST PAYLOAD - broken'},
                    self._success(3)]
        self.assertEqual(confirmed_payloads(messages, {'main': 'SO-1'}), [])


if __name__ == '__main__':
    unittest.main()
