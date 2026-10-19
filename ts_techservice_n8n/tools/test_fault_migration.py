import base64
import json
import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class FaultMigrationTests(unittest.TestCase):
    def setUp(self):
        self.env = Mock()
        self.orders = self.env.__getitem__ = Mock()
        self.order_model = Mock()
        self.attachment_model = Mock()
        self.orders.side_effect = {'sale.order': self.order_model, 'ir.attachment': self.attachment_model}.__getitem__
        self.order = types.SimpleNamespace(
            id=23, ts_fault_description='Lỗi cũ',
            ticket_id=types.SimpleNamespace(id=12, product_error_note='Lỗi mới', product_error_description=False),
        )
        self.order_model.search.return_value = [self.order]
        self.attachment_model.create.return_value.id = 77
        odoo = types.ModuleType('odoo')
        odoo.SUPERUSER_ID = 1
        odoo.api = Mock()
        odoo.api.Environment.return_value = self.env
        path = Path(__file__).parents[1] / 'migrations' / '17.0.1.0.3' / 'post-migrate.py'
        with patch.dict(sys.modules, {'odoo': odoo}):
            self.migrate = runpy.run_path(str(path))['migrate']

    def test_fresh_install_does_not_change_existing_data(self):
        self.migrate(Mock(), None)
        self.order_model.search.assert_not_called()

    def test_upgrade_backs_up_old_text_and_refreshes_only_changed_orders(self):
        cursor = Mock()
        self.migrate(cursor, '17.0.1.0.2')
        values = self.attachment_model.create.call_args.args[0]
        backup = json.loads(base64.b64decode(values['datas']))
        self.assertEqual(backup, [{
            'order_id': 23, 'ticket_id': 12,
            'old_description': 'Lỗi cũ', 'new_description': 'Lỗi mới',
        }])
        self.order_model.browse.assert_called_once_with([23])
        self.order_model.browse.return_value._compute_ts_fault_description.assert_called_once_with()
        cursor.commit.assert_not_called()

    def test_no_change_does_not_create_backup_or_write(self):
        self.order.ts_fault_description = 'Lỗi mới'
        self.migrate(Mock(), '17.0.1.0.2')
        self.attachment_model.create.assert_not_called()
        self.order_model.browse.assert_not_called()

    def test_failed_backup_prevents_description_update(self):
        self.attachment_model.create.side_effect = RuntimeError('Backup failed')
        with self.assertRaisesRegex(RuntimeError, 'Backup failed'):
            self.migrate(Mock(), '17.0.1.0.2')
        self.order_model.browse.assert_not_called()


if __name__ == '__main__':
    unittest.main()
