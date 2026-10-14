from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from odoo.addons.core_fastapi.dependencies import authorize_session_or_api_key
from odoo.addons.fastapi.dependencies import paging
from odoo.addons.fastapi.schemas import Paging
from odoo.tests.common import BaseCase

from ..routers import tickets


class TestTicketListResponse(BaseCase):
    def setUp(self):
        super().setUp()
        app = FastAPI()
        app.include_router(tickets.router, prefix='/api/v1/tickets')
        # Authentication is covered in core_fastapi; exercise the real response
        # serialization without requiring an HTTP session or database here.
        app.dependency_overrides[authorize_session_or_api_key] = lambda: None
        app.dependency_overrides[paging] = lambda: Paging(limit=80, offset=0)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.list_response = self.startPatcher(
            patch.object(tickets, 'get_list_api_response')
        )

    def test_both_list_routes_preserve_business_details(self):
        record = SimpleNamespace(
            uuid='ticket-uuid',
            name='HCM-2608-00188',
            subject='Repair',
            status='closed',
            owner_phone='0123456789',
            product_id=SimpleNamespace(
                id=7, name='Inverter', display_name='[MODEL-A] Inverter',
                default_code='MODEL-A',
            ),
            stock_name='SERIAL-OLD',
            stock_lot_id=SimpleNamespace(name='SERIAL-OLD'),
            replace_serial_number='SERIAL-NEW',
            step_id=SimpleNamespace(name='Repair', code='step_repair'),
            workflow_id=SimpleNamespace(name='Warranty', code='workflow_1'),
            board_serial_line_ids=[SimpleNamespace(
                id=11, sequence=10, old_board_serial='BOARD-OLD',
                new_board_serial='BOARD-NEW', board_serial_date=date(2026, 8, 11),
            )],
            saleperson_id=SimpleNamespace(id=13, name='Salesperson'),
            warranty=True,
            product_error_note='Motor error',
            survey_result_description='Survey completed',
            implementation_result='no_error',
            reception_project_code='PROJECT-001',
            ticket_rating_rate=5,
            ticket_rating_note='Completed',
            create_date=datetime(2026, 8, 11, 8, 14, 16),
            end_date=False,
        )
        self.list_response.return_value = ([record], 1219)
        for path in ('/api/v1/tickets', '/api/v1/tickets/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertEqual(body['count'], 1219)
                self.assertEqual(len(body['items']), 1)
                item = body['items'][0]
                self.assertEqual(item['uuid'], record.uuid)
                self.assertEqual(item['product_id']['default_code'], 'MODEL-A')
                self.assertEqual(item['stock_lot_id']['name'], 'SERIAL-OLD')
                self.assertEqual(item['stock_name'], 'SERIAL-OLD')
                self.assertEqual(item['serial_number'], 'SERIAL-OLD')
                self.assertEqual(item['replace_serial_number'], 'SERIAL-NEW')
                self.assertEqual(item['owner_phone'], record.owner_phone)
                self.assertEqual(item['step_id']['code'], 'step_repair')
                self.assertEqual(item['workflow_id']['code'], 'workflow_1')
                self.assertEqual(item['board_serial_line_ids'][0]['new_board_serial'], 'BOARD-NEW')
                self.assertEqual(item['board_serial_line_ids'][0]['board_serial_date'], '2026-08-11')
                self.assertEqual(item['saleperson_id']['name'], 'Salesperson')
                self.assertTrue(item['warranty'])
                self.assertEqual(item['product_error_note'], 'Motor error')
                self.assertEqual(item['survey_result_description'], 'Survey completed')
                self.assertEqual(item['implementation_result'], 'no_error')
                self.assertEqual(item['reception_project_code'], 'PROJECT-001')
                self.assertEqual(item['ticket_rating_rate'], 5)
                self.assertEqual(item['ticket_rating_note'], 'Completed')
                self.assertEqual(item['create_date'], '2026-08-11T08:14:16Z')
                self.assertFalse(item['end_date'])

    def test_missing_relations_and_empty_collections_are_serializable(self):
        self.list_response.return_value = ([SimpleNamespace(
            uuid='ticket-uuid', product_id=False, stock_lot_id=False,
            step_id=False, owner_id=False, saleperson_id=False,
            board_serial_line_ids=[], sale_order_ids=[],
            implementation_error_ids=[], ticket_step_assignee_ids=[],
            warranty_end_date=False,
        )], 1)
        response = self.client.get('/api/v1/tickets')
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()['items'][0]
        self.assertFalse(item['product_id'])
        self.assertFalse(item['step_id'])
        self.assertFalse(item['saleperson_id'])
        self.assertFalse(item['warranty_end_date'])
        self.assertEqual(item['board_serial_line_ids'], [])
        self.assertEqual(item['sale_order_ids'], [])
        self.assertEqual(item['implementation_error_ids'], [])

    def test_card_code_body_keeps_unpaginated_filter_and_full_response(self):
        self.list_response.return_value = ([SimpleNamespace(
            uuid='ticket-uuid', stock_name='SERIAL-001',
        )], 1)
        response = self.client.request(
            'GET', '/api/v1/tickets',
            params={'card_code': 'QUERY-CODE'},
            json={'card_code': 'BODY-CODE'},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['items'][0]['stock_name'], 'SERIAL-001')
        self.assertEqual(
            self.list_response.call_args.kwargs['domain'],
            [('owner_id.card_code', '=', 'BODY-CODE')],
        )
        self.assertIsNone(self.list_response.call_args.kwargs['paging'])

    def test_no_matching_tickets_returns_empty_page(self):
        self.list_response.return_value = ([], 0)
        response = self.client.get('/api/v1/tickets')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['count'], 0)
        self.assertEqual(response.json()['items'], [])

    def test_related_errors_keep_date_fields_and_unset_acceptance_status(self):
        self.list_response.return_value = ([SimpleNamespace(
            uuid='ticket-uuid',
            implementation_error_ids=[SimpleNamespace(
                id=21, uuid='error-uuid', description='Product error',
                date_detected=date(2026, 8, 11), date_resolved=False,
                acceptance_status=False, severity='low', state='new',
                detected_by=SimpleNamespace(uuid='user-uuid', name='Technician'),
                attachment_ids=[],
            )],
        )], 1)
        response = self.client.get('/api/v1/tickets')
        self.assertEqual(response.status_code, 200, response.text)
        error = response.json()['items'][0]['implementation_error_ids'][0]
        self.assertEqual(error['date_detected'], '2026-08-11')
        self.assertFalse(error['date_resolved'])
        self.assertFalse(error['acceptance_status'])
        self.assertEqual(error['detected_by']['name'], 'Technician')

    def test_empty_odoo_serial_relation_does_not_become_id_zero(self):
        class EmptyLot:
            _name = 'stock.lot'
            id = False
            name = False
            product_name = False

            def __bool__(self):
                return False

        self.list_response.return_value = ([SimpleNamespace(
            uuid='ticket-uuid', stock_name='SERIAL-001',
            stock_lot_id=SimpleNamespace(id=7, name='SERIAL-001'),
            new_stock_lot_id=EmptyLot(),
        )], 1)
        response = self.client.get('/api/v1/tickets')
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()['items'][0]
        self.assertEqual(item['serial_number'], 'SERIAL-001')
        self.assertEqual(item['stock_lot_id']['id'], 7)
        self.assertFalse(item['new_stock_lot_id'])

    def test_extension_serial_sync_and_defective_return_fields_are_preserved(self):
        self.list_response.return_value = ([SimpleNamespace(
            uuid='ticket-uuid', stock_name='SERIAL-001',
            ts_defective_return_status='received', ts_serial_synced=True,
            ts_last_serial_sync_at=datetime(2026, 10, 14, 8, 0),
            ts_last_serial_sync_note='Synced from SAP',
            bnk_replacement_serial_sync_note='Replacement received',
            manufacturer_warranty_month=24,
            manufacturer_warranty_end_date=False,
        )], 1)
        response = self.client.get('/api/v1/tickets')
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()['items'][0]
        self.assertEqual(item['ts_defective_return_status'], 'received')
        self.assertTrue(item['ts_serial_synced'])
        self.assertEqual(item['ts_last_serial_sync_at'], '2026-10-14T08:00:00Z')
        self.assertEqual(item['ts_last_serial_sync_note'], 'Synced from SAP')
        self.assertEqual(item['bnk_replacement_serial_sync_note'], 'Replacement received')
        self.assertEqual(item['manufacturer_warranty_month'], 24)
        self.assertFalse(item['manufacturer_warranty_end_date'])
        # An uninstalled extension supplies no attribute; it stays optional.
        self.assertIsNone(item['ts_return_so_ready'])
