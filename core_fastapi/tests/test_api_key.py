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
        self.initial_env = Mock()
        self.initial_env.context = {
            'lang': 'en_US',
            'allowed_company_ids': [999],
            'force_company': 999,
        }
        self.key_model = Mock()
        self.key_model._check_credentials.return_value = 42
        self.owner = Mock()
        self.owner.id = 42
        self.owner.active = True
        self.owner.lang = 'vi_VN'
        self.owner.tz = 'Asia/Ho_Chi_Minh'
        self.owner.company_ids.ids = [3, 7]
        self.users = Mock()
        self.users.sudo.return_value.browse.return_value.exists.return_value = self.owner
        self.initial_env.__getitem__ = Mock(side_effect={
            'res.users.apikeys': self.key_model,
            'res.users': self.users,
        }.__getitem__)
        self.authenticated_env = Mock()
        self.request.env = self.initial_env
        self.request.update_env.side_effect = self._update_env
        self.startPatcher(patch.object(dependencies, 'request', self.request))

    def _update_env(self, **kwargs):
        self.request.env = self.authenticated_env

    def _authorize(self, api_key=None):
        async def run():
            token = odoo_env_ctx.set(self.initial_env)
            try:
                user = await dependencies.authorize_session_or_api_key(api_key)
                return user, odoo_env_ctx.get()
            finally:
                odoo_env_ctx.reset(token)

        return asyncio.run(run())

    def test_valid_key_uses_owner_without_creating_session(self):
        user, env = self._authorize('test-key')

        self.assertIs(user, self.authenticated_env.user)
        self.assertIs(env, self.authenticated_env)
        self.key_model._check_credentials.assert_called_once_with(
            scope='rpc', key='test-key',
        )
        self.request.update_env.assert_called_once_with(
            user=42,
            context={
                'lang': 'vi_VN',
                'tz': 'Asia/Ho_Chi_Minh',
                'allowed_company_ids': [3, 7],
            },
            su=False,
        )
        self.assertIsNone(self.request.session.uid)
        self.request.session.authenticate.assert_not_called()

    def test_key_owner_takes_precedence_over_logged_in_user(self):
        self.request.session.uid = 99
        user, _env = self._authorize('test-key')

        self.assertIs(user, self.authenticated_env.user)
        self.assertEqual(self.request.update_env.call_args.kwargs['user'], 42)
        self.assertEqual(self.request.session.uid, 99)

    def test_missing_key_and_session_returns_401(self):
        with self.assertRaises(HTTPException) as caught:
            self._authorize()

        self.assertEqual(caught.exception.status_code, 401)
        self.key_model._check_credentials.assert_not_called()
        self.request.update_env.assert_not_called()

    def test_session_authentication_is_preserved_when_key_is_absent(self):
        self.request.session.uid = 99
        user, env = self._authorize()

        self.assertIs(user, self.initial_env.user)
        self.assertIs(env, self.initial_env)
        self.request.update_env.assert_not_called()

    def test_invalid_or_revoked_key_does_not_fall_back_to_session(self):
        self.request.session.uid = 99
        self.key_model._check_credentials.return_value = None
        with self.assertRaises(HTTPException) as caught:
            self._authorize('invalid-key')

        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

    def test_blank_key_is_rejected_even_with_session(self):
        self.request.session.uid = 99
        with self.assertRaises(HTTPException) as caught:
            self._authorize('   ')

        self.assertEqual(caught.exception.status_code, 401)
        self.key_model._check_credentials.assert_not_called()
        self.request.update_env.assert_not_called()

    def test_inactive_key_owner_is_rejected(self):
        self.owner.active = False
        with self.assertRaises(HTTPException) as caught:
            self._authorize('test-key')

        self.assertEqual(caught.exception.status_code, 401)
        self.request.update_env.assert_not_called()

    def test_key_does_not_authenticate_session_only_endpoints(self):
        self._authorize('test-key')
        with self.assertRaises(HTTPException) as caught:
            dependencies.authorize_session()

        self.assertEqual(caught.exception.status_code, 401)
