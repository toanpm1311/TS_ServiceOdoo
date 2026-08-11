from odoo import fields, models


class ResUsersNotification(models.Model):
    _name = 'res.users.notification'
    _description = 'Res Users Notification'
    _inherit = 'abstract.uuid'
    _rec_name = 'title'

    title = fields.Char(required=True)
    body = fields.Text(required=True)
    notification_type_id = fields.Many2one('notification.type')
    target_action = fields.Selection([
        ('open_detail_screen', 'Open Detail Screen'),
        ('open_list_screen', 'Open List Screen'),
    ])
    screen_type = fields.Selection([
        ('ticket_helpdesk', 'Ticket Helpdesk'),
    ])
    user_id = fields.Many2one(
        'res.users', required=True, ondelete='cascade', string="Sent To")
    sender_id = fields.Many2one('res.partner', string="Sent From")
    unread = fields.Boolean(default=True)
    push_notification_state = fields.Selection(
        [('failed', 'Failed'), ('success', 'Success')], help='The status of the notification push.')
    push_failed_reason = fields.Text(
        help='The failed reason when send push notification.')
    web_noti_state = fields.Selection(
        [('failed', 'Failed'), ('success', 'Success')],
        string='Web Notification State',
        help='The status of the notification on web.')
    web_noti_failed_reason = fields.Text(
        string='Web Notification Failed Reason',
        help='The failed reason when send notification on web.')
    active = fields.Boolean(default=True)
    # saves record info of the target record
    target_record_uuid = fields.Char()
