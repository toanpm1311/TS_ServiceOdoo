from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStockLotOwner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.product'].create({
            'name': 'Owner synchronization test product',
            'tracking': 'serial',
        })
        cls.buyer, cls.local_owner, cls.sap_owner = cls.env['res.partner'].create([
            {'name': 'Initial Buyer', 'is_company': True},
            {'name': 'Corrected Owner', 'is_company': True},
            {'name': 'SAP Owner'},
        ])

    def _create_lot(self, name, **values):
        return self.env['stock.lot'].create({
            'name': name,
            'product_id': self.product.id,
            'company_id': self.env.company.id,
            'buyer_id': self.buyer.id,
            **values,
        })

    def test_initial_owner_defaults_to_buyer(self):
        lot = self._create_lot('OWNER-DEFAULT')
        self.assertEqual(lot.owner_id, self.buyer)
        self.assertFalse(lot.owner_manual_override)

    def test_manual_owner_survives_sap_refresh(self):
        lot = self._create_lot('OWNER-MANUAL')
        lot.write({'owner_id': self.local_owner.id})
        lot._write_sap_serial_values({
            'owner_id': self.sap_owner.id,
            'warranty_month': 24,
        })
        self.assertEqual(lot.owner_id, self.local_owner)
        self.assertTrue(lot.owner_manual_override)
        self.assertEqual(lot.buyer_id, self.buyer)
        self.assertEqual(lot.warranty_month, 24)

    def test_unmodified_owner_follows_sap(self):
        lot = self._create_lot('OWNER-SAP')
        lot._write_sap_serial_values({'owner_id': self.sap_owner.id})
        self.assertEqual(lot.owner_id, self.sap_owner)
        self.assertFalse(lot.owner_manual_override)
        lot._write_sap_serial_values({'owner_id': self.buyer.id})
        self.assertEqual(lot.owner_id, self.buyer)

    def test_buyer_fallback_preserves_existing_owner(self):
        lot = self._create_lot('OWNER-FALLBACK', owner_id=self.local_owner.id)
        lot._write_sap_serial_values(
            {'owner_id': self.buyer.id}, owner_is_fallback=True,
        )
        self.assertEqual(lot.owner_id, self.local_owner)

    def test_multi_record_refresh_preserves_only_manual_owner(self):
        manual_lot = self._create_lot('OWNER-MIXED-MANUAL')
        sap_lot = self._create_lot('OWNER-MIXED-SAP')
        manual_lot.write({'owner_id': self.local_owner.id})
        (manual_lot | sap_lot)._write_sap_serial_values({
            'owner_id': self.sap_owner.id,
        })
        self.assertEqual(manual_lot.owner_id, self.local_owner)
        self.assertEqual(sap_lot.owner_id, self.sap_owner)
        self.assertFalse(sap_lot.owner_manual_override)
