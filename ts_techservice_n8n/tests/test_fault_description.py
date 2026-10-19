from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestQuotationFaultDescription(TransactionCase):
    def _ticket(self, note='Lỗi relay', description='Lỗi ban đầu', name='HNI-2610-00446'):
        return self.env['ticket.helpdesk'].new({
            'name': name,
            'stock_name': 'F12208003570',
            'product_error_note': note,
            'product_error_description': description,
        })

    def test_ticket_correction_updates_existing_quotation_and_report(self):
        ticket = self._ticket()
        order = self.env['sale.order'].new({'ticket_id': ticket})
        self.assertEqual(order.ts_fault_description, 'Lỗi relay')
        ticket.product_error_note = 'Lỗi relay. Kèm logger.'
        self.assertEqual(order.ts_fault_description, 'Lỗi relay. Kèm logger.')
        self.assertEqual(order._get_ts_fault_sections()[0]['description'], 'Lỗi relay. Kèm logger.')

    def test_fallback_and_ticket_replacement(self):
        ticket = self._ticket(note=False)
        order = self.env['sale.order'].new({'ticket_id': ticket})
        self.assertEqual(order.ts_fault_description, 'Lỗi ban đầu')
        ticket.product_error_description = 'Đã sửa nội dung lỗi'
        self.assertEqual(order.ts_fault_description, 'Đã sửa nội dung lỗi')
        order.ticket_id = self._ticket(note='Lỗi ticket khác')
        self.assertEqual(order.ts_fault_description, 'Lỗi ticket khác')
        order.ticket_id = False
        self.assertFalse(order.ts_fault_description)

    def test_cleared_ticket_fault_does_not_keep_old_text(self):
        ticket = self._ticket()
        order = self.env['sale.order'].new({'ticket_id': ticket})
        self.assertTrue(order.ts_fault_description)
        ticket.update({'product_error_note': False, 'product_error_description': False})
        self.assertFalse(order.ts_fault_description)
        self.assertEqual(order._get_ts_fault_sections(), [])

    def test_manual_text_survives_unrelated_updates_until_ticket_fault_changes(self):
        ticket = self._ticket()
        order = self.env['sale.order'].new({'ticket_id': ticket})
        order.ts_fault_description = 'Nội dung riêng cho báo giá'
        ticket.name = 'HNI-2610-00447'
        self.assertEqual(order.ts_fault_description, 'Nội dung riêng cho báo giá')
        ticket.product_error_note = 'Kết quả kiểm tra mới'
        self.assertEqual(order.ts_fault_description, 'Kết quả kiểm tra mới')

    def test_ticket_correction_does_not_reset_send_generation(self):
        ticket = self._ticket()
        order = self.env['sale.order'].new({
            'ticket_id': ticket, 'ts_quotation_generation': 'existing-send',
        })
        self.assertEqual(order.ts_fault_description, 'Lỗi relay')
        ticket.product_error_note = 'Lỗi đã sửa'
        self.assertEqual(order.ts_fault_description, 'Lỗi đã sửa')
        self.assertEqual(order.ts_quotation_generation, 'existing-send')
