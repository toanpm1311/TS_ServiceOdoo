from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.dat_sale.models.sale_order_line import SaleOrderLine as DatSaleOrderLine
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
            'detailed_type': 'product',
        })

    def _quotation_line(self, price, state='draft', sap_status=False, with_ticket=True, status='draft'):
        # Transient records exercise the ORM price compute without creating a
        # real ticket or running its external notification/workflow hooks.
        order = self.env['sale.order'].new({
            'partner_id': self.env.user.partner_id.id,
            'state': state,
            'status': status,
            'sap_status': sap_status,
            'date_order': fields.Datetime.to_datetime('2026-10-15 08:00:00'),
        })
        if with_ticket:
            order.ticket_id = self.env['ticket.helpdesk'].new({})
        line = self.env['sale.order.line'].new({
            'order_id': order,
            'product_id': self.product.id,
            'product_uom': self.product.uom_id.id,
            'product_uom_qty': 1.0,
            'price_unit': price,
        })
        order.order_line = line
        return line

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

    def test_buyer_change_preserves_draft_prices_including_zero(self):
        buyer = self.env['res.partner'].create({'name': 'Replacement quotation buyer'})
        for price in (500000.0, 2957000.0, 0.0):
            with self.subTest(price=price):
                line = self._quotation_line(price)
                line.order_id.partner_id = buyer
                # Buyer synchronization invalidates the order's pricelist and
                # currency. Model that header recompute even if its value did
                # not change, as happens with two VND buyers.
                line.order_id.currency_id = line.order_id.currency_id
                self.assertEqual(line.price_unit, price)

    def test_header_company_recompute_preserves_draft_price(self):
        line = self._quotation_line(3800000.0)
        line.order_id.company_id = line.order_id.company_id
        self.assertEqual(line.price_unit, 3800000.0)

    def test_direct_customer_and_pricelist_change_preserves_all_lines(self):
        buyer = self.env['res.partner'].create({'name': 'New direct quotation buyer'})
        order = self._quotation_line(500000.0).order_id
        currency = order.currency_id
        pricelist = self.env['product.pricelist'].create({
            'name': 'Replacement buyer pricelist',
            'currency_id': currency.id,
        })
        lines = self.env['sale.order.line']
        for price in (500000.0, 2957000.0, 0.0):
            lines |= self.env['sale.order.line'].new({
                'order_id': order,
                'product_id': self.product.id,
                'product_uom': self.product.uom_id.id,
                'product_uom_qty': 1.0,
                'price_unit': price,
                'discount': 10.0,
            })
        order.order_line = lines
        before = [(line.price_unit, line.discount, line.price_subtotal) for line in lines]
        order.update({'partner_id': buyer.id, 'pricelist_id': pricelist.id})
        order._compute_currency_id()
        self.assertEqual(
            [(line.price_unit, line.discount, line.price_subtotal) for line in lines], before,
        )

    def test_dat_approved_order_preserves_price_while_odoo_still_draft(self):
        for status in ('confirmed', 'cancelled', 'rejected'):
            for price in (500000.0, 0.0):
                with self.subTest(status=status, price=price):
                    line = self._quotation_line(price, status=status)
                    line.product_uom_qty = 2.0
                    line._compute_price_unit()
                    self.assertEqual(line.price_unit, price)

    def test_dat_sale_itself_preserves_approved_prices(self):
        # Exercise the common module directly: protection must also work
        # without the optional service-pricing override.
        for status in ('confirmed', 'cancelled', 'rejected'):
            line = self._quotation_line(2957000.0, status=status)
            DatSaleOrderLine._compute_price_unit(line)
            self.assertEqual(line.price_unit, 2957000.0)

    def _saved_quotation(self, ticket=False):
        order = self.env['sale.order'].create({
            'partner_id': self.env.user.partner_id.id,
            'ticket_id': ticket.id if ticket else False,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom': self.product.uom_id.id,
                'product_uom_qty': 1.0,
                'price_unit': price,
                'discount': 10.0,
            }) for price in (500000.0, 2957000.0, 0.0)],
        })
        self.assertEqual(order.order_line.mapped('price_unit'), [500000.0, 2957000.0, 0.0])
        return order

    def _saved_price_snapshot(self, order):
        self.env.flush_all()
        order.order_line.invalidate_recordset(['price_unit', 'discount', 'price_subtotal'])
        order.invalidate_recordset(['amount_total'])
        return (
            [(line.id, line.price_unit, line.discount, line.price_subtotal) for line in order.order_line],
            order.amount_total,
        )

    def test_saved_quotation_customer_write_preserves_prices(self):
        order = self._saved_quotation()
        before = self._saved_price_snapshot(order)
        pricelist = self.env['product.pricelist'].create({
            'name': 'Saved buyer price regression',
            'currency_id': order.currency_id.id,
        })
        buyer = self.env['res.partner'].create({
            'name': 'Saved replacement buyer',
            'property_product_pricelist': pricelist.id,
        })
        order.write({'partner_id': buyer.id})
        self.assertEqual(self._saved_price_snapshot(order), before)
        self.assertEqual(order.pricelist_id, pricelist)

    def test_ticket_owner_sync_preserves_saved_quotation_prices(self):
        lot = self.env['stock.lot'].create({
            'name': 'TS-PRICE-OWNER-SYNC',
            'product_id': self.product.id,
            'company_id': self.env.company.id,
            'owner_id': self.env.user.partner_id.id,
        })
        priority = self.env['ticket.priority'].create({'name': 'Price regression priority'})
        # Suppress external receipt notifications and SAP reason lookup; keep
        # real ticket, SO, owner synchronization and ORM dependency handling.
        with (
            patch.object(type(self.env['ticket.helpdesk']), '_send_zns_notification'),
            patch.object(type(self.env['sale.order']), '_sync_all_sap_voucher_reasons'),
        ):
            ticket = self.env['ticket.helpdesk'].create({
                'customer_id': self.env.user.partner_id.id,
                'customer_phone': '0000000000',
                'subject': 'Owner synchronization price regression',
                'stock_lot_id': lot.id,
                'priority_id': priority.id,
            })
            order = self._saved_quotation(ticket)
            before = self._saved_price_snapshot(order)
            buyer = self.env['res.partner'].create({
                'name': 'New ticket owner', 'phone': '0000000001',
            })
            ticket.write({'owner_id': buyer.id})
            self.assertEqual(order.partner_id, buyer)
            self.assertEqual(order.partner_invoice_id, buyer)
            self.assertEqual(order.partner_shipping_id, buyer)
            self.assertEqual(self._saved_price_snapshot(order), before)

    def test_new_service_line_and_explicit_price_refresh_still_use_mapping(self):
        service = self.env['product.product'].create({
            'name': 'Mapped regression service',
            'default_code': 'TS-MAPPED-PRICE-REGRESSION',
            'detailed_type': 'service',
            'list_price': 1.0,
        })
        price_item = self.env['dat.price.list.item'].create({
            'item_code': 'TS-MODEL-SERVICE-REGRESSION',
            'price': 850000.0,
            'currency_id': self.env.company.currency_id.id,
        })
        self.env['ts.service.price'].create({
            'main_product_id': self.product.id,
            'service_product_id': service.id,
            'price_item_id': price_item.id,
        })
        line = self._quotation_line(0.0)
        line.order_id.main_product_id = self.product
        line.order_id.currency_id = self.env.company.currency_id
        line.product_id = service
        line._compute_price_unit()
        self.assertEqual(line.price_unit, 850000.0)
        line.price_unit = 500000.0
        updated, missing = line._apply_dat_price_list()
        self.assertEqual((updated, missing), (1, 0))
        self.assertEqual(line.price_unit, 850000.0)

    def test_quantity_change_still_reprices_draft_line(self):
        line = self._quotation_line(500000.0)
        line.product_uom_qty = 2.0
        self.assertEqual(line.price_unit, 1.0)

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
