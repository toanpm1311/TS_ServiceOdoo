from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from odoo.addons.core_fastapi.dependencies import authorize_session, authorize_session_or_api_key
from odoo.addons.core_fastapi.routers import base
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
        app.dependency_overrides[authorize_session] = lambda: None
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
            ticket_step_status_ids=[], checklist_ids=[],
            task_allocation_ids=[], kpi_coefficient_ids=[],
            technical_proposal_ids=[], external_document_ids=[],
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
        for name in ('ticket_step_status_ids', 'checklist_ids', 'task_allocation_ids',
                     'kpi_coefficient_ids', 'technical_proposal_ids',
                     'external_document_ids'):
            self.assertEqual(item[name], [])

    def test_progress_preserves_repeated_steps_assignees_and_sla_on_list_and_detail(self):
        step = SimpleNamespace(id=7, name='Repair quotation', code='step_quotation')
        users = [SimpleNamespace(uuid='user-1', name='Technician 1'),
                 SimpleNamespace(uuid='user-2', name='Technician 2')]
        rows = [SimpleNamespace(
            id=11, step_id=step, step_name=step.name, assignee_ids=users,
            start_date=datetime(2026, 5, 28, 2, 46, 9),
            deadline=datetime(2026, 5, 28, 7, 46, 9),
            end_date=datetime(2026, 5, 29, 1, 33, 14),
            time_sla=4.0, time_spent=6.7833333333, status='done',
            hold_date=False, hold_time=0.0,
            time_alert=datetime(2026, 5, 28, 6, 46, 9), time_check=False,
            deadline_notification_sent=True,
        ), SimpleNamespace(
            id=12, step_id=step, step_name=step.name, assignee_ids=users[1:],
            start_date=datetime(2026, 5, 29, 1, 33, 14),
            deadline=False, end_date=False, time_sla=0.0, time_spent=0.0,
            status='in_progress', hold_date=False, hold_time=0.0,
            time_alert=False, time_check=datetime(2026, 5, 29, 2, 0),
            deadline_notification_sent=False,
        )]
        record = SimpleNamespace(uuid='ticket-uuid', ticket_step_status_ids=rows)
        self.list_response.return_value = ([record], 1)
        request = Mock()
        request.env.__getitem__ = Mock()
        request.env['ticket.helpdesk'].validate_by_uuid.return_value = record
        with patch.object(base, 'request', request):
            for path in ('/api/v1/tickets', '/api/v1/tickets/',
                         '/api/v1/tickets/ticket-uuid'):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200, response.text)
                    body = response.json()
                    item = body['items'][0] if 'items' in body else body
                    progress = item['ticket_step_status_ids']
                    self.assertEqual([row['id'] for row in progress], [11, 12])
                    self.assertEqual([row['step_id']['id'] for row in progress], [7, 7])
                    self.assertEqual(progress[0]['step_name'], step.name)
                    self.assertEqual([user['uuid'] for user in progress[0]['assignee_ids']],
                                     ['user-1', 'user-2'])
                    self.assertEqual(progress[0]['start_date'], '2026-05-28T02:46:09Z')
                    self.assertEqual(progress[0]['deadline'], '2026-05-28T07:46:09Z')
                    self.assertEqual(progress[0]['end_date'], '2026-05-29T01:33:14Z')
                    self.assertEqual(progress[0]['time_sla'], 4.0)
                    self.assertAlmostEqual(progress[0]['time_spent'], 6.7833333333)
                    self.assertEqual(progress[0]['status'], 'done')
                    self.assertFalse(progress[0]['hold_date'])
                    self.assertEqual(progress[0]['hold_time'], 0.0)
                    self.assertEqual(progress[0]['time_alert'], '2026-05-28T06:46:09Z')
                    self.assertTrue(progress[0]['deadline_notification_sent'])
                    self.assertEqual(progress[1]['status'], 'in_progress')
                    self.assertFalse(progress[1]['deadline'])
                    self.assertFalse(progress[1]['end_date'])
                    self.assertEqual(progress[1]['time_spent'], 0.0)
                    self.assertEqual(progress[1]['time_check'], '2026-05-29T02:00:00Z')

    def test_progress_supports_all_statuses_and_empty_assignees(self):
        statuses = ('not_started', 'in_progress', 'on_hold', 'done', 'rejected', False)
        self.list_response.return_value = ([SimpleNamespace(
            uuid='ticket-uuid',
            ticket_step_status_ids=[SimpleNamespace(
                id=index, status=status, assignee_ids=[], step_id=False,
                start_date=False, deadline=False, end_date=False,
            ) for index, status in enumerate(statuses, 1)],
        )], 1)
        response = self.client.get('/api/v1/tickets')
        self.assertEqual(response.status_code, 200, response.text)
        progress = response.json()['items'][0]['ticket_step_status_ids']
        self.assertEqual([row['status'] for row in progress], list(statuses))
        self.assertTrue(all(row['assignee_ids'] == [] for row in progress))
        self.assertTrue(all(row['step_id'] is False for row in progress))

    def test_quotation_feedback_results_are_preserved_on_list_and_detail(self):
        request = Mock()
        request.env.__getitem__ = Mock()
        for feedback, comment, note in (
            ('agree', False, 'Customer accepted the quotation'),
            ('refuse', 'Customer declined the price', 'Do not proceed'),
            (False, False, False),
        ):
            record = SimpleNamespace(
                uuid='ticket-uuid', sale_order_feedback=feedback,
                sale_order_feedback_comment=comment, note_SO=note,
                sap_sale_order_number='SO-001', sap_so_status='open',
            )
            self.list_response.return_value = ([record], 1)
            request.env['ticket.helpdesk'].validate_by_uuid.return_value = record
            with patch.object(base, 'request', request):
                for path in ('/api/v1/tickets', '/api/v1/tickets/',
                             '/api/v1/tickets/ticket-uuid'):
                    with self.subTest(feedback=feedback, path=path):
                        response = self.client.get(path)
                        self.assertEqual(response.status_code, 200, response.text)
                        body = response.json()
                        item = body['items'][0] if 'items' in body else body
                        self.assertEqual(item['sale_order_feedback'], feedback)
                        self.assertEqual(item['sale_order_feedback_comment'], comment)
                        self.assertEqual(item['note_SO'], note)
                        self.assertEqual(item['sap_sale_order_number'], 'SO-001')
                        self.assertEqual(item['sap_so_status'], 'open')

    def test_work_checklist_results_are_preserved_on_list_and_detail(self):
        record = SimpleNamespace(
            uuid='ticket-uuid', checklist_count=2,
            checklist_ids=[SimpleNamespace(
                id=21, code='CL-001', name='Check motor', is_done=True,
                done_date=datetime(2026, 8, 11, 8, 21, 1), note='Motor passed inspection',
            ), SimpleNamespace(
                id=22, code='CL-002', name='Check wiring', is_done=False,
                done_date=False, note=False,
            )],
            survey_result_description='Survey result',
            completed_task_description='Completed work result',
            implementation_work_note='Implementation result note',
        )
        self.list_response.return_value = ([record], 1)
        request = Mock()
        request.env.__getitem__ = Mock()
        request.env['ticket.helpdesk'].validate_by_uuid.return_value = record
        with patch.object(base, 'request', request):
            for path in ('/api/v1/tickets', '/api/v1/tickets/',
                         '/api/v1/tickets/ticket-uuid'):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200, response.text)
                    body = response.json()
                    item = body['items'][0] if 'items' in body else body
                    self.assertEqual(item['checklist_count'], 2)
                    done, pending = item['checklist_ids']
                    self.assertIs(done['is_done'], True)
                    self.assertEqual(done['done_date'], '2026-08-11T08:21:01Z')
                    self.assertEqual(done['note'], 'Motor passed inspection')
                    self.assertIs(pending['is_done'], False)
                    self.assertIs(pending['done_date'], False)
                    self.assertIs(pending['note'], False)
                    # These are the source fields used for the printed checklist's
                    # inspection result, in the report's fallback order.
                    self.assertEqual(item['survey_result_description'], 'Survey result')
                    self.assertEqual(item['completed_task_description'], 'Completed work result')
                    self.assertEqual(item['implementation_work_note'], 'Implementation result note')

    def test_checklists_allocations_proposals_and_document_history_are_preserved(self):
        user = SimpleNamespace(uuid='technician-uuid', name='Technician')
        self.list_response.return_value = ([SimpleNamespace(
            uuid='ticket-uuid', waiting_for_assignment=False, total_time_spent=12.5,
            ticket_step_ids=[SimpleNamespace(id=7, name='Repair')],
            checklist_count=1, checklist_ids=[SimpleNamespace(
                id=21, sequence=10, code='CL-001', name='Check motor',
                step_id=SimpleNamespace(id=7, name='Repair'),
                assigned_user_id=user, is_done=True,
                done_date=datetime(2026, 8, 11, 8, 21, 1), note='Checked',
            )],
            task_allocation_ids=[SimpleNamespace(
                id=31, sequence=1, user_id=user, weight=0.5, point=10.0, note='Repair',
            )],
            kpi_coefficient_ids=[SimpleNamespace(id=41, user_id=user, coefficient='1.5')],
            material_proposal_create_count=2,
            technical_proposal_ids=[SimpleNamespace(
                id=51, name='BOM-001', version=2, bom_type='automation',
                tp_create_date=datetime(2026, 8, 11, 8, 0), tp_create_by=user,
                is_locked=False, is_final_version=True,
                technical_solution_description='Replace motor',
                technical_proposal_line_ids=[SimpleNamespace(
                    id=61, sequence=1, product_id=SimpleNamespace(id=9, name='Motor'),
                    default_code='MOTOR-001', uom_id=SimpleNamespace(id=1, name='Units'),
                    quantity=2.0, onhand_quantity=5.0, note='Required',
                )], attachment_ids=[],
            )],
            external_document_count=1, external_document_ids=[SimpleNamespace(
                id=71, sale_order_id=SimpleNamespace(id=3, name='SO-001'),
                operation='dxvt', operation_name='Material dispatch',
                document_number='DOC-001', create_date=datetime(2026, 8, 11, 8, 30),
            )],
        )], 1)
        response = self.client.get('/api/v1/tickets')
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()['items'][0]
        self.assertEqual(item['total_time_spent'], 12.5)
        self.assertFalse(item['waiting_for_assignment'])
        self.assertEqual(item['ticket_step_ids'][0]['id'], 7)
        self.assertEqual(item['checklist_count'], 1)
        checklist = item['checklist_ids'][0]
        self.assertEqual(checklist['code'], 'CL-001')
        self.assertEqual(checklist['assigned_user_id']['uuid'], user.uuid)
        self.assertTrue(checklist['is_done'])
        self.assertEqual(checklist['done_date'], '2026-08-11T08:21:01Z')
        self.assertEqual(item['task_allocation_ids'][0]['weight'], 0.5)
        self.assertEqual(item['task_allocation_ids'][0]['point'], 10.0)
        self.assertEqual(item['kpi_coefficient_ids'][0]['coefficient'], '1.5')
        self.assertEqual(item['material_proposal_create_count'], 2)
        proposal = item['technical_proposal_ids'][0]
        self.assertEqual(proposal['version'], 2)
        self.assertTrue(proposal['is_final_version'])
        self.assertEqual(proposal['tp_create_by']['uuid'], user.uuid)
        self.assertEqual(proposal['technical_solution_description'], 'Replace motor')
        line = proposal['technical_proposal_line_ids'][0]
        self.assertEqual(line['product_id']['name'], 'Motor')
        self.assertEqual(line['uom_id']['name'], 'Units')
        self.assertEqual(line['quantity'], 2.0)
        self.assertEqual(item['external_document_count'], 1)
        document = item['external_document_ids'][0]
        self.assertEqual(document['document_number'], 'DOC-001')
        self.assertEqual(document['sale_order_id']['name'], 'SO-001')
        self.assertEqual(document['create_date'], '2026-08-11T08:30:00Z')

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
        for name in ('ticket_step_status_ids', 'checklist_ids', 'task_allocation_ids',
                     'kpi_coefficient_ids', 'technical_proposal_ids'):
            self.assertIsNone(item[name])
