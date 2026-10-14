from unittest.mock import patch

from odoo.tests.common import TransactionCase

from ..dependencies import API_KEY_PARAMETER
from ..models import ir_config_parameter


class TestApiKeyParameter(TransactionCase):
    def setUp(self):
        super().setUp()
        self.parameters = self.env['ir.config_parameter'].sudo()
        self.parameters.search([('key', '=', API_KEY_PARAMETER)]).unlink()

    def test_registry_hook_creates_missing_random_key_and_clears_cached_miss(self):
        self.assertFalse(self.parameters.get_param(API_KEY_PARAMETER))

        self.parameters._register_hook()

        value = self.parameters.get_param(API_KEY_PARAMETER)
        self.assertRegex(value, r'^[A-Za-z0-9_-]{43}$')
        self.assertEqual(
            self.parameters.search_count([('key', '=', API_KEY_PARAMETER)]), 1,
        )

    def test_repeated_registry_hooks_preserve_generated_key(self):
        self.parameters._register_hook()
        value = self.parameters.get_param(API_KEY_PARAMETER)

        self.parameters._register_hook()

        self.assertEqual(self.parameters.get_param(API_KEY_PARAMETER), value)
        self.assertEqual(
            self.parameters.search_count([('key', '=', API_KEY_PARAMETER)]), 1,
        )

    def test_existing_custom_value_is_not_changed(self):
        self.parameters.set_param(API_KEY_PARAMETER, 'user-chosen-secret')
        record = self.parameters.search([('key', '=', API_KEY_PARAMETER)])
        original_write_date = record.write_date

        with patch.object(ir_config_parameter.secrets, 'token_urlsafe') as generate:
            self.parameters._register_hook()

        generate.assert_not_called()
        self.assertEqual(record.value, 'user-chosen-secret')
        self.assertEqual(record.write_date, original_write_date)

    def test_blank_existing_value_is_not_replaced(self):
        self.parameters.set_param(API_KEY_PARAMETER, '   ')

        self.parameters._register_hook()

        self.assertEqual(self.parameters.get_param(API_KEY_PARAMETER), '   ')

    def test_concurrent_insert_keeps_the_other_workers_value(self):
        self.parameters.set_param(API_KEY_PARAMETER, 'other-worker-secret')
        self.parameters.flush_model()

        # Simulate another worker inserting after the initial existence check.
        with patch.object(type(self.parameters), 'search', return_value=self.parameters.browse()):
            self.parameters._ensure_core_api_key()

        self.assertEqual(self.parameters.get_param(API_KEY_PARAMETER), 'other-worker-secret')
        self.assertEqual(
            self.parameters.search_count([('key', '=', API_KEY_PARAMETER)]), 1,
        )
