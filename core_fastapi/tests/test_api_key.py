import asyncio
from unittest.mock import Mock, patch

from fastapi import HTTPException
from odoo import SUPERUSER_ID
from odoo.addons.fastapi.context import odoo_env_ctx
from odoo.tests.common import BaseCase

from .. import dependencies


class TestApiKey(BaseCase):
    def setUp(self):
        super().setUp()
        self.request = Mock()
        self.request.session.uid = None
        self.request.httprequest.path = '/api/v1/tickets'
        self.request.httprequest.method = 'GET'
        self.initial_env = Mock()
        self.initial_env.context = {
            'lang': 'en_US',
            'allowed_company_ids': [999],
            'force_company': 999,
        }
        self.parameter_values = {
            'core_fastapi.api_key': 'test-key',
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
        self.endpoint.root_path = '/api/v1'
        self.endpoint.user_id = self.owner
        self.endpoint.company_id.id = 3
        self.endpoints = Mock()
        self.endpoints.sudo.return_value.browse.return_value.exists.return_value = self.endpoint
        self.companies = Mock()
        self.companies.sudo.return_value.search.return_value.ids = [3, 7]
        self.initial_env.__getitem__ = Mock(side_effect={
            'ir.config_parameter': self.parameters,
            'fastapi.endpoint': self.endpoints,
            'res.company': self.companies,
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

    def test_valid_key_grants_read_access_without_creating_session(self):
        user, env = self._authorize('test-key')

        self.assertIs(user, self.authenticated_env.user)
        self.assertIs(env, self.authenticated_env)
        self.parameters.sudo.return_value.get_param.assert_called_once_with(
            'core_fastapi.api_key',
        )
        self.endpoints.sudo.return_value.browse.assert_called_once_with(
            12,
        )
        self.request.update_env.assert_called_once_with(
            user=SUPERUSER_ID,
            context={
                'lang': 'en_US',
                'allowed_company_ids': [3, 7],
            },
            su=True,
        )
        self.companies.sudo.return_value.search.assert_called_once_with([], order='id')
        self.assertIsNone(self.request.session.uid)
        self.request.session.authenticate.assert_not_called()

    def test_key_read_access_does_not_depend_on_logged_in_user(self):
        self.request.session.uid = 99
        user, _env = self._authorize('test-key')

        self.assertIs(user, self.authenticated_env.user)
        self.assertEqual(self.request.update_env.call_args.kwargs['user'], SUPERUSER_ID)
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

    def test_key_read_access_does_not_depend_on_endpoint_user_or_company(self):
        self.owner.active = False
        for user in (None, self.owner):
            with self.subTest(endpoint_user=user):
                self.endpoint.user_id = user
                self.endpoint.company_id.id = 999
                authenticated_user, _env = self._authorize('test-key')
                self.assertIs(authenticated_user, self.authenticated_env.user)
                self.assertTrue(self.request.update_env.call_args.kwargs['su'])
                self.assertEqual(
                    self.request.update_env.call_args.kwargs['context']['allowed_company_ids'],
                    [3, 7],
                )

    def test_key_cannot_elevate_non_get_requests_even_with_session(self):
        self.request.session.uid = 99
        for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'):
            with self.subTest(method=method):
                self.request.httprequest.method = method
                with self.assertRaises(HTTPException) as caught:
                    self._authorize('test-key')
                self.assertEqual(caught.exception.status_code, 401)
                self.request.update_env.assert_not_called()
                self.parameters.sudo.assert_not_called()
                self.assertEqual(self.request.session.uid, 99)

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
        self.parameter_values['core_fastapi.api_key'] = 'replacement-key'
        with self.assertRaises(HTTPException) as caught:
            self._authorize('test-key')
        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

        user, _env = self._authorize('replacement-key')
        self.assertIs(user, self.authenticated_env.user)
        self.request.update_env.reset_mock()
        del self.parameter_values['core_fastapi.api_key']
        with self.assertRaises(HTTPException) as caught:
            self._authorize('replacement-key')
        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

    def test_surrounding_whitespace_is_trimmed(self):
        self.parameter_values['core_fastapi.api_key'] = ' test-key\n'
        user, _env = self._authorize(' test-key ')

        self.assertIs(user, self.authenticated_env.user)
        self.request.update_env.assert_called_once()

    def test_tickets_route_accepts_optional_trailing_slash(self):
        for request_path in ('/api/v1/tickets', '/api/v1/tickets/'):
            with self.subTest(requested=request_path):
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
                self.companies.sudo.assert_not_called()

    def test_route_uses_mounted_app_root_independently_of_secret_value(self):
        self.endpoint.root_path = '/api/v2'
        self.request.httprequest.path = '/api/v2/tickets'
        user, _env = self._authorize('test-key')
        self.assertIs(user, self.authenticated_env.user)

    def test_inactive_endpoint_is_rejected(self):
        self.endpoint.active = False
        with self.assertRaises(HTTPException) as caught:
            self._authorize('test-key')
        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

    def test_endpoint_without_company_reads_all_database_companies(self):
        self.endpoint.company_id = None
        self._authorize('test-key')
        self.assertEqual(
            self.request.update_env.call_args.kwargs['context']['allowed_company_ids'],
            [3, 7],
        )

    def test_non_ascii_secret_value_is_compared_without_server_error(self):
        self.parameter_values['core_fastapi.api_key'] = 'khóa-thử'
        user, _env = self._authorize('khóa-thử')
        self.assertIs(user, self.authenticated_env.user)
        self.request.update_env.reset_mock()
        with self.assertRaises(HTTPException) as caught:
            self._authorize('khóa-sai')
        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

    def test_fixed_parameter_accepts_user_chosen_secret_value(self):
        self.parameter_values['core_fastapi.api_key'] = 'my-random-local-secret'
        user, _env = self._authorize('my-random-local-secret')
        self.assertIs(user, self.authenticated_env.user)
        self.parameters.sudo.return_value.get_param.assert_called_once_with('core_fastapi.api_key')

    def test_old_secret_to_path_parameter_does_not_authenticate(self):
        del self.parameter_values['core_fastapi.api_key']
        self.parameter_values['test'] = 'api/v1/tickets'
        for value in ('test', 'api/v1/tickets'):
            with self.subTest(value=value), self.assertRaises(HTTPException) as caught:
                self._authorize(value)
            self.assertEqual(caught.exception.status_code, 401)
            self.request.update_env.assert_not_called()

    def test_header_must_contain_secret_value_not_parameter_name(self):
        self.request.session.uid = 99
        for value in ('core_fastapi.api_key', 'core_fastapi.api_key_endpoint',
                      'core_fastapi.api_key_user_login'):
            with self.subTest(value=value):
                with self.assertRaises(HTTPException) as caught:
                    self._authorize(value)
                self.assertEqual(caught.exception.status_code, 401)
                self.request.update_env.assert_not_called()

    def test_other_system_parameters_cannot_grant_access(self):
        self.parameter_values['another.api_key'] = 'other-secret'
        self.parameter_values['web.base.url'] = 'http://localhost:5050'
        for value in ('other-secret', 'another.api_key', 'http://localhost:5050'):
            with self.subTest(value=value), self.assertRaises(HTTPException) as caught:
                self._authorize(value)
            self.assertEqual(caught.exception.status_code, 401)
            self.request.update_env.assert_not_called()

    def test_key_does_not_authenticate_session_only_endpoints(self):
        self._authorize('test-key')
        with self.assertRaises(HTTPException) as caught:
            dependencies.authorize_session()

        self.assertEqual(caught.exception.status_code, 401)
