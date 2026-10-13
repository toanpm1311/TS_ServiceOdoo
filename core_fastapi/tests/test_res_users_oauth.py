import json

from odoo import exceptions
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResUsersOAuth(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env.ref('core_fastapi.provider_azure')
        users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.oauth_uid = 'archived-oauth-uid'
        cls.archived_user = users.create({
            'name': 'Archived OAuth User',
            'login': 'archived.oauth@example.com',
            'email': 'oauth.user@example.com',
            'active': False,
            'oauth_provider_id': cls.provider.id,
            'oauth_uid': cls.oauth_uid,
            'oauth_access_token': 'old-token',
        })
        cls.invited_user = users.create({
            'name': 'Invited OAuth User',
            'login': 'oauth.user@example.com',
            'email': 'oauth.user@example.com',
        })
        cls.invited_user.partner_id.signup_prepare(signup_type='signup')
        cls.invite_token = cls.invited_user.partner_id.signup_token

    def _signin(self, *, email='oauth.user@example.com', token=None):
        state = {'t': token} if token else {}
        return self.env['res.users']._auth_oauth_signin(
            self.provider.id,
            {
                'user_id': self.oauth_uid,
                'email': email,
                'name': 'OAuth User',
            },
            {
                'access_token': 'new-token',
                'state': json.dumps(state),
            },
        )

    def test_transfer_archived_oauth_identity_to_matching_invited_user(self):
        login = self._signin(token=self.invite_token)

        self.assertEqual(login, self.invited_user.login)
        self.assertFalse(self.archived_user.oauth_provider_id)
        self.assertFalse(self.archived_user.oauth_uid)
        self.assertFalse(self.archived_user.oauth_access_token)
        self.assertEqual(self.invited_user.oauth_provider_id, self.provider)
        self.assertEqual(self.invited_user.oauth_uid, self.oauth_uid)
        self.assertEqual(self.invited_user.oauth_access_token, 'new-token')

    def test_keep_archived_oauth_identity_without_invite(self):
        with self.assertRaises(exceptions.AccessDenied):
            self._signin()

        self.assertEqual(self.archived_user.oauth_provider_id, self.provider)
        self.assertEqual(self.archived_user.oauth_uid, self.oauth_uid)
        self.assertEqual(self.archived_user.oauth_access_token, 'old-token')

    def test_keep_archived_oauth_identity_when_email_does_not_match(self):
        with self.assertRaises(exceptions.AccessDenied):
            self._signin(email='another.user@example.com', token=self.invite_token)

        self.assertEqual(self.archived_user.oauth_provider_id, self.provider)
        self.assertEqual(self.archived_user.oauth_uid, self.oauth_uid)
        self.assertEqual(self.archived_user.oauth_access_token, 'old-token')
