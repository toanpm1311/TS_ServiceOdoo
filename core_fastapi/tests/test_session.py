from unittest.mock import Mock, patch

from odoo import http
from odoo.addons.web.controllers.session import Session
from odoo.exceptions import AccessDenied, AccessError
from odoo.tests.common import BaseCase

from ..controllers.session import ApiSession


class TestApiSession(BaseCase):
    def setUp(self):
        super().setUp()
        self.controller = ApiSession()
        self.odoo_authenticate = self.startPatcher(
            patch.object(Session, 'authenticate')
        )

    def test_domain_filter_selects_database_without_client_db(self):
        request = Mock()
        request.httprequest.environ = {'HTTP_HOST': 'service.example.com:443'}
        result = {'uid': 42, 'db': 'service'}
        self.odoo_authenticate.return_value = result
        with patch.object(http, 'request', request), \
                patch.object(http, 'config', {
                    'dbfilter': '^%d$', 'db_name': '',
                }), \
                patch('odoo.service.db.list_dbs', return_value=[
                    'other', 'service',
                ]) as list_dbs:
            response = self.controller.authenticate('user@example.com', 'secret')

        self.assertIs(response, result)
        list_dbs.assert_called_once_with(True)
        self.odoo_authenticate.assert_called_once_with(
            'service', 'user@example.com', 'secret'
        )

    def test_configured_database_works_when_database_listing_is_disabled(self):
        # Exercise Odoo's actual database selection with listing hidden.
        # A configured db_name avoids needing a PostgreSQL connection here.
        with patch.dict(http.config.options, {
            'dbfilter': '', 'db_name': 'production', 'list_db': False,
        }):
            self.controller.authenticate('user@example.com', 'secret')

        self.odoo_authenticate.assert_called_once_with(
            'production', 'user@example.com', 'secret'
        )

    def test_missing_or_ambiguous_database_rejects_login(self):
        for databases in ([], ['one', 'two']):
            with self.subTest(databases=databases), \
                    patch.object(http, 'db_list', return_value=databases), \
                    self.assertRaises(AccessError):
                self.controller.authenticate('user@example.com', 'secret')

        self.odoo_authenticate.assert_not_called()

    def test_invalid_credentials_preserve_odoo_access_denied(self):
        self.odoo_authenticate.side_effect = AccessDenied()
        with patch.object(http, 'db_list', return_value=['production']), \
                self.assertRaises(AccessDenied):
            self.controller.authenticate('user@example.com', 'wrong')

    def test_mfa_pending_result_is_not_reported_as_success(self):
        result = {'uid': None}
        self.odoo_authenticate.return_value = result
        with patch.object(http, 'db_list', return_value=['production']):
            response = self.controller.authenticate('user@example.com', 'secret')

        self.assertIs(response, result)
