from odoo import _, http
from odoo.addons.web.controllers.session import Session
from odoo.exceptions import AccessError


class ApiSession(http.Controller):
    @http.route(
        '/api/session/authenticate',
        type='json',
        auth='none',
        methods=['POST'],
    )
    def authenticate(self, login, password):
        """Authenticate against the only database allowed for the request host."""
        # Match Odoo's monodb selection, even when database listing is hidden.
        # Do not use a client-supplied database or an existing session to choose.
        databases = http.db_list(force=True)
        if len(databases) != 1:
            raise AccessError(_(
                'This domain must resolve to exactly one database. '
                'Please configure dbfilter or db_name on the Odoo server.'
            ))

        # Reuse Odoo's authentication, MFA handling and session cookie lifecycle.
        return Session().authenticate(databases[0], login, password)
