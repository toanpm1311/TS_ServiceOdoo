from unittest.mock import Mock, patch

import requests

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNotificationDelivery(TransactionCase):
    def setUp(self):
        super().setUp()
        self.queue = self.env['ts.n8n.notification'].sudo()
        self.order = self.env['sale.order'].create({
            'partner_id': self.env.user.partner_id.id,
            'ts_quotation_generation': 'test-generation',
        })
        self.env['ir.config_parameter'].sudo().set_param('ts_techservice_n8n.holidays', '')
        self.queue._enqueue(
            event_key='delivery-test:%s' % self.order.id, event_type='quotation_sent',
            recipient='sale@example.com', title='Test quotation', body='Test quotation body',
            ticket=self.env['ticket.helpdesk'], order=self.order,
        )
        self.messages = self.queue.search([('order_id', '=', self.order.id)])

    def test_due_date_starts_after_both_channels(self):
        email = self.messages.filtered(lambda message: message.channel == 'email')
        teams = self.messages - email
        email._ts_mark_sent()
        self.assertFalse(self.order.ts_quotation_sent_at)
        teams._ts_mark_sent()
        self.assertTrue(self.order.ts_quotation_sent_at)
        self.assertGreater(self.order.ts_response_due_at, self.order.ts_quotation_sent_at)

    def test_repeated_enqueue_does_not_duplicate_channels(self):
        self.queue._enqueue(
            event_key=self.messages[0].event_key, event_type='quotation_sent',
            recipient='sale@example.com', title='Test', body='Test',
            ticket=self.env['ticket.helpdesk'], order=self.order,
        )
        self.assertEqual(self.queue.search_count([('order_id', '=', self.order.id)]), 2)

    def test_wrong_acknowledgement_is_failure(self):
        message = self.messages[0]
        response = Mock()
        response.json.return_value = {'delivered': True, 'event_id': 'different-event'}
        with patch('odoo.addons.ts_techservice_n8n.models.notification.requests.post', return_value=response):
            message._ts_dispatch_one('https://n8n.example.com/webhook/test', 'test-token')
        self.assertEqual(message.state, 'failed')
        self.assertFalse(self.order.ts_quotation_sent_at)

    def test_timeout_does_not_automatically_retry_successful_channel(self):
        succeeded = self.messages[0]
        failed = self.messages[1]
        succeeded._ts_mark_sent()
        with patch('odoo.addons.ts_techservice_n8n.models.notification.requests.post', side_effect=requests.Timeout):
            failed._ts_dispatch_one('https://n8n.example.com/webhook/test', 'test-token')
        self.messages.action_retry()
        self.assertEqual(succeeded.state, 'sent')
        self.assertEqual(failed.state, 'pending')

    def test_response_before_reminder_dispatch_cancels_delivery(self):
        message = self.messages[0]
        message.write({'event_type': 'quotation_reminder'})
        self.order.ts_sales_response = 'received'
        with patch('odoo.addons.ts_techservice_n8n.models.notification.requests.post') as post:
            message._ts_dispatch_one('https://n8n.example.com/webhook/test', 'test-token')
            post.assert_not_called()
        self.assertEqual(message.state, 'cancelled')

    def test_rejected_quotation_is_not_sent(self):
        self.order.status = 'rejected'
        with patch('odoo.addons.ts_techservice_n8n.models.notification.requests.post') as post:
            self.messages[0]._ts_dispatch_one('https://n8n.example.com/webhook/test', 'test-token')
            post.assert_not_called()
        self.assertEqual(self.messages[0].state, 'cancelled')
