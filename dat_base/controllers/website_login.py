from odoo import http, _
from odoo.addons.web.controllers.home import Home
import logging
_logger = logging.getLogger(__name__)

class CustomHome(Home):
    @http.route('/web/login', type='http', auth="public")
    def web_login(self, redirect=None, **kw):
        try:
            response = super(CustomHome, self).web_login(redirect, **kw)
            if 'error' in response.qcontext and response.qcontext['error'] == 'Wrong login/password':
                response.qcontext['error'] = _("This account has been disabled")
            return response
        except Exception as e:
            _logger.error("Error in web_login: %s", str(e))
            raise