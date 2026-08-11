from odoo import fields, models
from firebase_admin import messaging


class ResPartnerFirebaseMessage(models.TransientModel):
    _inherit = "res.partner.firebase.message"

    def channel_firebase_notifications_with_data(self, data: dict):
        res_partner_ids = self._context.get('active_ids')

        device_ids = self.env['res.users'].sudo().search([
            ('partner_id', 'in', res_partner_ids)
        ]).mapped('mail_firebase_tokens').mapped('token')

        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=self.title or '',
                body=self.body or ''
            ),
            data=data,
            tokens=device_ids
        )

        response = messaging.send_each_for_multicast(message)

        if response:
            notification_id = self.env['mobile.app.push.notification'].sudo().create({
                'name': self.title,
                'body': self.body,
                'send_notification_to': 'to_specefic',
                'partner_ids': [(6, 0, res_partner_ids)],
                'state': 'done',
            })

            self.env['push.notification.log.history'].sudo().create({
                'notification_id': notification_id.id,
                'date_send': fields.Datetime.now(),
                'notification_state': 'success',
            })

            responses = response.responses

            for idx, resp in enumerate(responses):
                state = 'success' if resp.success else 'failed'
                device_token = device_ids[idx]

                self.env['push.notification.log.partner'].sudo().create({
                    'notification_id': notification_id.id,
                    'name': self.title,
                    'body': self.body,
                    'partner_id': res_partner_ids[0],
                    'date_send': fields.Datetime.now(),
                    'notification_state': state,
                    'device_token': device_token
                })
