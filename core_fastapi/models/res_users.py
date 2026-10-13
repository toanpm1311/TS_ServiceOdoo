import json
import logging
import re

from odoo import _, api, exceptions, models


_logger = logging.getLogger(__name__)


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

    @api.model
    def _get_oauth_invited_user(self, validation, params):
        """Resolve and validate the active user targeted by an OAuth invite."""
        try:
            state = json.loads(params.get('state') or '{}')
        except (TypeError, ValueError) as error:
            raise exceptions.AccessDenied() from error

        token = state.get('t')
        if not token:
            raise exceptions.AccessDenied()

        try:
            partner = self.env['res.partner'].sudo()._signup_retrieve_partner(
                token,
                check_validity=True,
                raise_exception=True,
            )
        except exceptions.UserError as error:
            raise exceptions.AccessDenied() from error

        invited_user = partner.with_context(active_test=False).user_ids.filtered('active')[:1]
        if not invited_user:
            raise exceptions.AccessDenied()

        # Never overwrite an OAuth identity already assigned to the invited
        # user. Such a conflict needs an administrator to choose the account.
        if invited_user.oauth_provider_id or invited_user.oauth_uid:
            _logger.warning(
                "Blocked OAuth transfer to user id=%s because it already has an OAuth identity",
                invited_user.id,
            )
            raise exceptions.AccessDenied()

        oauth_email = (validation.get('email') or '').strip().casefold()
        invited_emails = {
            value.strip().casefold()
            for value in (invited_user.login, invited_user.email, partner.email)
            if value and value.strip()
        }
        if not oauth_email or oauth_email not in invited_emails:
            _logger.warning(
                "Blocked OAuth transfer to invited user id=%s because the verified email does not match",
                invited_user.id,
            )
            raise exceptions.AccessDenied()

        return invited_user

    @api.model
    def _auth_oauth_signin(self, provider, validation, params):
        """Move an archived OAuth identity only when a matching invite proves ownership.

        Odoo's standard lookup excludes archived users, while the database
        uniqueness constraint includes them. Without this guard, accepting an
        invitation for a replacement user raises a UniqueViolation at commit
        time and returns HTTP 500.
        """
        oauth_uid = validation['user_id']
        archived_oauth_user = self.with_context(active_test=False).search([
            ('oauth_provider_id', '=', provider),
            ('oauth_uid', '=', oauth_uid),
            ('active', '=', False),
        ])
        if not archived_oauth_user:
            return super()._auth_oauth_signin(provider, validation, params)

        if len(archived_oauth_user) != 1 or self.env.context.get('no_user_creation'):
            raise exceptions.AccessDenied()

        invited_user = self._get_oauth_invited_user(validation, params)

        # Flush the archived owner first so PostgreSQL's non-deferrable unique
        # constraint permits the standard signup flow to assign the identity
        # to the invited user. The savepoint restores the old mapping if signup
        # fails for any reason.
        with self.env.cr.savepoint():
            archived_oauth_user.write({
                'oauth_provider_id': False,
                'oauth_uid': False,
                'oauth_access_token': False,
            })
            archived_oauth_user.flush_recordset([
                'oauth_provider_id',
                'oauth_uid',
                'oauth_access_token',
            ])
            login = super()._auth_oauth_signin(provider, validation, params)

        _logger.info(
            "Transferred OAuth provider id=%s from archived user id=%s to invited user id=%s",
            provider,
            archived_oauth_user.id,
            invited_user.id,
        )
        return login
