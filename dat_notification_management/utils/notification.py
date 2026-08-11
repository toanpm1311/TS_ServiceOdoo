from odoo import _
from odoo.exceptions import AccessError

from ..models.res_users_notification import ResUsersNotification


def get_my_notifications_domain(user, filter_kwargs: dict):
    domain = [('user_id', '=', user.id)]
    unread = filter_kwargs.get('unread')
    if unread is not None:
        domain.append(('unread', '=', unread))
    return domain


def validate_notification(current_user, noti: ResUsersNotification):
    if noti.user_id != current_user:
        raise AccessError(_('Permission Denied'))
