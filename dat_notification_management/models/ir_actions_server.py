from odoo import fields, models


class IrActionsServer(models.Model):
    _inherit = 'ir.actions.server'

    is_changes_updated_notification = fields.Boolean(default=False)

    def _compute_name(self):
        # use the action name instead of the automatic name for the notification actions
        actions_without_noti = self.filtered_domain(
            [('is_changes_updated_notification', '=', False)])
        super(IrActionsServer, actions_without_noti)._compute_display_name()

    def check_user_allowed_noti(self, user, notification_type):
        self.ensure_one()
        if notification_type not in user.allowed_notification_type_ids:
            return False
        if notification_type.code == 'changes_updated':
            return self.check_user_allowed_changes_updated_noti(user)
        return True

    def check_user_allowed_changes_updated_noti(self, user):
        self.ensure_one()
        return self in user.allowed_changes_updated_notification_action_ids

    def filter_users_allowed_changes_updated_noti(self, users):
        self.ensure_one()
        return users.filtered(lambda user: self.check_user_allowed_changes_updated_noti(user))
