import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class PriceMigrationTests(unittest.TestCase):
    migration_version = '17.0.1.0.2'
    installed_version = '17.0.1.0.1'

    def setUp(self):
        self.env = Mock()
        self.api = Mock()
        self.api.Environment.return_value = self.env
        odoo = types.ModuleType('odoo')
        odoo.api = self.api
        odoo.SUPERUSER_ID = 1
        self.recovery = types.ModuleType('odoo.addons.ts_techservice_n8n.tools.restore_so_prices')
        self.recovery.build_plan = Mock(return_value={'repairs': [], 'skipped': []})
        self.recovery.apply_plan = Mock(return_value={'updated': 0, 'backup_attachment_id': False})
        self.recovery.backup_plan = Mock(return_value=types.SimpleNamespace(id=77))
        path = Path(__file__).parents[1] / 'migrations' / self.migration_version / 'post-migrate.py'
        with patch.dict(sys.modules, {'odoo': odoo, self.recovery.__name__: self.recovery}):
            self.migrate = runpy.run_path(str(path))['migrate']

    def test_fresh_install_does_not_recover_prices(self):
        self.migrate(Mock(), None)
        self.recovery.build_plan.assert_not_called()
        self.recovery.apply_plan.assert_not_called()

    def test_upgrade_restores_and_reuses_backup_without_committing(self):
        cursor = Mock()
        self.recovery.apply_plan.return_value = {'updated': 3, 'backup_attachment_id': 42}
        self.migrate(cursor, self.installed_version)
        self.api.Environment.assert_called_once_with(cursor, 1, {})
        self.recovery.apply_plan.assert_called_once_with(
            self.env, self.recovery.build_plan.return_value)
        self.recovery.backup_plan.assert_not_called()
        cursor.commit.assert_not_called()

    def test_skipped_lines_are_reported_even_without_repairs(self):
        self.migrate(Mock(), self.installed_version)
        self.recovery.backup_plan.assert_called_once_with(
            self.env, self.recovery.build_plan.return_value)

    def test_failure_propagates_to_roll_back_upgrade(self):
        cursor = Mock()
        self.recovery.apply_plan.side_effect = ValueError('Data changed')
        with self.assertRaisesRegex(ValueError, 'Data changed'):
            self.migrate(cursor, self.installed_version)
        cursor.commit.assert_not_called()
        self.recovery.backup_plan.assert_not_called()


class BuyerChangePriceMigrationTests(PriceMigrationTests):
    migration_version = '17.0.1.0.4'
    installed_version = '17.0.1.0.3'


if __name__ == '__main__':
    unittest.main()
