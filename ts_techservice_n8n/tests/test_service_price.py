from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestServicePriceConfirmation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.product'].create({
            'name': 'Confirmation price regression',
            'default_code': 'TS-CONFIRM-PRICE-REGRESSION',
            'list_price': 1.0,
        })

    def _quotation_line(self, price, state='draft', sap_status=False, with_ticket=True):
        # Transient records exercise the ORM price compute without creating a
        # real ticket or running its external notification/workflow hooks.
        order = self.env['sale.order'].new({
            'partner_id': self.env.user.partner_id.id,
            'state': state,
            'sap_status': sap_status,
            'date_order': fields.Datetime.to_datetime('2026-10-15 08:00:00'),
        })
        if with_ticket:
            order.ticket_id = self.env['ticket.helpdesk'].new({})
        return self.env['sale.order.line'].new({
            'order_id': order,
            'product_id': self.product.id,
            'product_uom': self.product.uom_id.id,
            'product_uom_qty': 1.0,
            'price_unit': price,
        })

    def test_confirmation_date_preserves_agreed_prices_including_zero(self):
        for price in (500000.0, 2957000.0, 0.0):
            with self.subTest(price=price):
                line = self._quotation_line(price)
                line.order_id.update({
                    'state': 'sale',
                    'date_order': fields.Datetime.to_datetime('2026-10-15 09:00:00'),
                })
                line._compute_price_unit()
                self.assertEqual(line.price_unit, price)

    def test_draft_date_change_does_not_reprice_negotiated_lines(self):
        for price in (42000000.0, 3800000.0, 0.0):
            with self.subTest(price=price):
                line = self._quotation_line(price)
                line.order_id.date_order = fields.Datetime.to_datetime('2026-10-16 09:00:00')
                # Access the field after dependency invalidation, rather than
                # calling the compute directly and bypassing ORM scheduling.
                self.assertEqual(line.price_unit, price)

    def test_sap_document_preserves_price_before_state_is_updated(self):
        line = self._quotation_line(500000.0, sap_status='Main: CTH-26-006227')
        line._compute_price_unit()
        self.assertEqual(line.price_unit, 500000.0)

    def test_mixed_recordset_still_prices_draft_quotation(self):
        confirmed = self._quotation_line(500000.0, state='sale')
        draft = self._quotation_line(500000.0)
        (confirmed | draft)._compute_price_unit()
        self.assertEqual(confirmed.price_unit, 500000.0)
        self.assertEqual(draft.price_unit, 1.0)

    def test_orders_without_ticket_keep_standard_price_computation(self):
        line = self._quotation_line(500000.0, state='sale', with_ticket=False)
        line._compute_price_unit()
        self.assertEqual(line.price_unit, 1.0)
