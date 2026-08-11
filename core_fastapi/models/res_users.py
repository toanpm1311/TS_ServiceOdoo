import re

from odoo import _, api, exceptions, models


class ResUsers(models.Model):
    _name = 'res.users'
    _inherit = ['abstract.uuid', 'res.users']

    @property
    def email_constrains(self):
        """
        Regular expression pattern for validating the user's login (email).

        This property is used by the `_check_login` constraint to ensure
        that the login field, which is typically an email address,
        conforms to a specific format. If this property returns a regex
        pattern, `_check_login` will validate the login against it.
        If it returns `None`, the regex validation in `_check_login` is skipped.

        :returns: A string representing the regex pattern or None.
        :rtype: str | None
        """
        return None

    @api.constrains('login')
    def _check_login(self):
        for rec in self:
            if self.email_constrains and not re.fullmatch(self.email_constrains, rec.login):
                raise exceptions.UserError(_('Login email is invalid.'))
