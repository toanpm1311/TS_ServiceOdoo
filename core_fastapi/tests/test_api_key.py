import asyncio
from unittest.mock import Mock, patch

from fastapi import HTTPException
from odoo.addons.fastapi.context import odoo_env_ctx
from odoo.tests.common import BaseCase

from .. import dependencies


class TestApiKey(BaseCase):
    def setUp(self):
        super().setUp()
        self.request = Mock()
        self.request.session.uid = None
        self.request.httprequest.path = '/api/v1/tickets'
        self.initial_env = Mock()
        self.initial_env.context = {
            'lang': 'en_US',
            'allowed_company_ids': [999],
            'force_company': 999,
        }
        self.parameter_values = {
            'test-key': '/api/v1/tickets',
        }
        self.parameters = Mock()
        self.parameters.sudo.return_value.get_param.side_effect = (
            self.parameter_values.get
        )
        self.owner = Mock()
        self.owner.id = 42
        self.owner.active = True
        self.owner._is_public.return_value = False
        self.owner.lang = 'vi_VN'
        self.owner.tz = 'Asia/Ho_Chi_Minh'
        self.owner.company_ids.ids = [3, 7]
        self.endpoint = Mock()
        self.endpoint.active = True
        self.endpoint.user_id = self.owner
        self.endpoint.company_id.id = 3
        self.endpoints = Mock()
        self.endpoints.sudo.return_value.browse.return_value.exists.return_value = self.endpoint
        self.initial_env.__getitem__ = Mock(side_effect={
            'ir.config_parameter': self.parameters,
            'fastapi.endpoint': self.endpoints,
        }.__getitem__)
        self.authenticated_env = Mock()
        self.request.env = self.initial_env
        self.request.update_env.side_effect = self._update_env
        self.startPatcher(patch.object(dependencies, 'request', self.request))

    def _update_env(self, **kwargs):
        self.request.env = self.authenticated_env

    def _authorize(self, api_key=None):
        # Each call represents a new HTTP request with its initial environment.
        self.request.env = self.initial_env

        async def run():
            token = odoo_env_ctx.set(self.initial_env)
            try:
                user = await dependencies.authorize_session_or_api_key(
                    endpoint_id=12, api_key=api_key,
                )
                return user, odoo_env_ctx.get()
            finally:
                odoo_env_ctx.reset(token)

        return asyncio.run(run())

    def test_valid_key_uses_endpoint_user_without_creating_session(self):
        user, env = self._authorize('test-key')

        self.assertIs(user, self.authenticated_env.user)
        self.assertIs(env, self.authenticated_env)
        self.parameters.sudo.return_value.get_param.assert_called_once_with(
            'test-key',
        )
        self.endpoints.sudo.return_value.browse.assert_called_once_with(
            12,
        )
        self.request.update_env.assert_called_once_with(
            user=42,
            context={
                'lang': 'vi_VN',
                'tz': 'Asia/Ho_Chi_Minh',
                'allowed_company_ids': [3],
            },
            su=False,
        )
        self.assertIsNone(self.request.session.uid)
        self.request.session.authenticate.assert_not_called()

    def test_endpoint_user_takes_precedence_over_logged_in_user(self):
        self.request.session.uid = 99
        user, _env = self._authorize('test-key')

        self.assertIs(user, self.authenticated_env.user)
        self.assertEqual(self.request.update_env.call_args.kwargs['user'], 42)
        self.assertEqual(self.request.session.uid, 99)

    def test_missing_key_and_session_returns_401(self):
        with self.assertRaises(HTTPException) as caught:
            self._authorize()

        self.assertEqual(caught.exception.status_code, 401)
        self.parameters.sudo.assert_not_called()
        self.request.update_env.assert_not_called()

    def test_session_authentication_is_preserved_when_key_is_absent(self):
        self.request.session.uid = 99
        user, env = self._authorize()

        self.assertIs(user, self.initial_env.user)
        self.assertIs(env, self.initial_env)
        self.parameters.sudo.assert_not_called()
        self.request.update_env.assert_not_called()

    def test_invalid_or_revoked_key_does_not_fall_back_to_session(self):
        self.request.session.uid = 99
        with self.assertRaises(HTTPException) as caught:
            self._authorize('invalid-key')

        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

    def test_blank_key_is_rejected_even_with_session(self):
        self.request.session.uid = 99
        with self.assertRaises(HTTPException) as caught:
            self._authorize('   ')

        self.assertEqual(caught.exception.status_code, 401)
        self.endpoints.sudo.assert_not_called()
        self.request.update_env.assert_not_called()

    def test_inactive_endpoint_user_is_rejected(self):
        self.owner.active = False
        with self.assertRaises(HTTPException) as caught:
            self._authorize('test-key')

        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

    def test_native_inactive_public_execution_user_is_supported(self):
        self.owner.active = False
        self.owner._is_public.return_value = True
        user, _env = self._authorize('test-key')
        self.assertIs(user, self.authenticated_env.user)
        self.assertFalse(self.request.update_env.call_args.kwargs['su'])

    def test_missing_or_blank_configuration_is_rejected_even_with_session(self):
        self.request.session.uid = 99
        for parameter in self.parameter_values:
            original = self.parameter_values[parameter]
            for value in (None, '', '   '):
                with self.subTest(parameter=parameter, value=value):
                    self.parameter_values[parameter] = value
                    with self.assertRaises(HTTPException) as caught:
                        self._authorize('test-key')
                    self.assertEqual(caught.exception.status_code, 401)
                    self.request.update_env.assert_not_called()
                    self.endpoints.sudo.assert_not_called()
            self.parameter_values[parameter] = original

    def test_missing_endpoint_is_rejected(self):
        self.endpoints.sudo.return_value.browse.return_value.exists.return_value = None
        with self.assertRaises(HTTPException) as caught:
            self._authorize('test-key')

        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

    def test_changed_or_deleted_key_revokes_previous_key(self):
        self.request.session.uid = 99
        self.parameter_values['replacement-key'] = self.parameter_values.pop('test-key')
        with self.assertRaises(HTTPException) as caught:
            self._authorize('test-key')
        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

        user, _env = self._authorize('replacement-key')
        self.assertIs(user, self.authenticated_env.user)
        self.request.update_env.reset_mock()
        del self.parameter_values['replacement-key']
        with self.assertRaises(HTTPException) as caught:
            self._authorize('replacement-key')
        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

    def test_surrounding_whitespace_is_trimmed(self):
        self.parameter_values['test-key'] = ' /api/v1/tickets\n'
        user, _env = self._authorize(' test-key ')

        self.assertIs(user, self.authenticated_env.user)
        self.request.update_env.assert_called_once()

    def test_path_accepts_optional_leading_and_trailing_slashes(self):
        for configured_path in ('api/v1/tickets', '/api/v1/tickets', '/api/v1/tickets/'):
            for request_path in ('/api/v1/tickets', '/api/v1/tickets/'):
                with self.subTest(configured=configured_path, requested=request_path):
                    self.parameter_values['test-key'] = configured_path
                    self.request.httprequest.path = request_path
                    user, _env = self._authorize('test-key')
                    self.assertIs(user, self.authenticated_env.user)

    def test_other_paths_are_rejected_even_with_session(self):
        self.request.session.uid = 99
        for path in ('/api/v1/tickets/123', '/api/v1/tickets/masterdata',
                     '/api/v1/tickets-other', '/api/v2/tickets'):
            with self.subTest(path=path):
                self.request.httprequest.path = path
                with self.assertRaises(HTTPException) as caught:
                    self._authorize('test-key')
                self.assertEqual(caught.exception.status_code, 401)
                self.request.update_env.assert_not_called()
                self.endpoints.sudo.assert_not_called()

    def test_changing_endpoint_restricts_the_key_immediately(self):
        self.parameter_values['test-key'] = '/api/v2/tickets'
        with self.assertRaises(HTTPException) as caught:
            self._authorize('test-key')
        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

    def test_inactive_endpoint_is_rejected(self):
        self.endpoint.active = False
        with self.assertRaises(HTTPException) as caught:
            self._authorize('test-key')
        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

    def test_endpoint_without_execution_user_is_rejected(self):
        self.endpoint.user_id = None
        with self.assertRaises(HTTPException) as caught:
            self._authorize('test-key')
        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

    def test_endpoint_without_company_uses_execution_users_companies(self):
        self.endpoint.company_id = None
        self._authorize('test-key')
        self.assertEqual(
            self.request.update_env.call_args.kwargs['context']['allowed_company_ids'],
            [3, 7],
        )

    def test_non_ascii_key_is_looked_up_without_server_error(self):
        self.parameter_values['khóa-thử'] = self.parameter_values.pop('test-key')
        user, _env = self._authorize('khóa-thử')
        self.assertIs(user, self.authenticated_env.user)
        self.request.update_env.reset_mock()
        with self.assertRaises(HTTPException) as caught:
            self._authorize('khóa-sai')
        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

    def test_screenshot_configuration_uses_one_parameter(self):
        self.parameter_values = {'test': 'api/v1/tickets'}
        self.parameters.sudo.return_value.get_param.side_effect = self.parameter_values.get
        user, _env = self._authorize('test')
        self.assertIs(user, self.authenticated_env.user)
        self.parameters.sudo.return_value.get_param.assert_called_once_with('test')

    def test_multiple_keys_have_independent_paths_and_revocation(self):
        self.parameter_values['second-key'] = '/api/v2/tickets'
        with self.assertRaises(HTTPException) as caught:
            self._authorize('second-key')
        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()
        self.request.httprequest.path = '/api/v2/tickets'
        user, _env = self._authorize('second-key')
        self.assertIs(user, self.authenticated_env.user)
        del self.parameter_values['second-key']
        self.request.httprequest.path = '/api/v1/tickets'
        user, _env = self._authorize('test-key')
        self.assertIs(user, self.authenticated_env.user)

    def test_previous_configuration_names_are_not_accepted_as_secret_keys(self):
        self.request.session.uid = 99
        for name in ('core_fastapi.api_key', 'core_fastapi.api_key_endpoint',
                     'core_fastapi.api_key_user_login'):
            with self.subTest(name=name):
                self.parameter_values[name] = '/api/v1/tickets'
                with self.assertRaises(HTTPException) as caught:
                    self._authorize(name)
                self.assertEqual(caught.exception.status_code, 401)
                self.request.update_env.assert_not_called()
                self.parameters.sudo.assert_not_called()

    def test_key_does_not_authenticate_session_only_endpoints(self):
        self._authorize('test-key')
        with self.assertRaises(HTTPException) as caught:
            dependencies.authorize_session()

        self.assertEqual(caught.exception.status_code, 401)
