from odoo import _
from odoo.exceptions import ValidationError
from odoo.http import request

from ..schemas import TicketHelpdeskCreate, TicketMasterData


def get_ticket_masterdata_response_field(master_field: TicketMasterData):
    key_field, value_field = 'uuid', 'name'
    if master_field in [TicketMasterData.customer_id, TicketMasterData.department_id]:
        value_field = 'complete_name'
        if master_field in [TicketMasterData.customer_id]:
            key_field = 'card_code'
    elif master_field in [TicketMasterData.state_id, TicketMasterData.step_id]:
        key_field = 'code'
    elif master_field == TicketMasterData.product_id:
        key_field = 'default_code'
    return key_field, value_field


def create_ticket(body: TicketHelpdeskCreate):
    cleaned_input = clean_creation_input(body)
    create_ticket_wizard = request.env['create.ticket.wizard'].create(
        cleaned_input)
    ticket_ids = create_ticket_wizard._action_create()
    ticket_ids.create_source = body.create_source
    return ticket_ids


def clean_creation_input(body: TicketHelpdeskCreate):
    state_id = request.env['res.country.state'].search(
        [('code', '=', body.state_code)], limit=1)

    branch_id = request.env['res.company'].validate_by_uuid(
        body.branch_id)

    priority_id = request.env['ticket.priority'].search(
        [('code', '=', body.priority_code)], limit=1)

    department_id = request.env['hr.department'].validate_by_uuid(
        body.department_id)

    ticket_type_id = request.env['helpdesk.type'].validate_by_uuid(
        body.ticket_type_id)

    attachment_model = request.env['ir.attachment']
    ir_attachment_vals_list = attachment_model.extract_attachment_vals_from_pydantic(
        body.install_attachment_ids)
    attachments = attachment_model.create(ir_attachment_vals_list)

    customer_id = request.env['res.partner'].search(
        [('card_code', '=', body.customer_card_code)], limit=1)

    technical_solution_attachment_vals_list = attachment_model.extract_attachment_vals_from_pydantic(
        body.technical_solution_attachment_ids)
    technical_solution_attachments = attachment_model.create(
        technical_solution_attachment_vals_list)

    stock_lot = request.env['stock.lot'].search(
        [('name', '=', body.serial_number)], limit=1)
    if not stock_lot:
        raise ValidationError(_(
            "Không tìm thấy số serial %s trên TechService. Vui lòng đồng bộ serial trước khi tạo phiếu."
        ) % (body.serial_number or ''))
    if not stock_lot.owner_id or not stock_lot.buyer_id:
        raise ValidationError(_(
            "Số serial %s chưa có khách hàng/người sở hữu. Vui lòng đồng bộ lại serial trước khi tạo phiếu."
        ) % body.serial_number)
    ticket_product_vals = {
        'serial_number': stock_lot.id,
        'product_id': stock_lot.product_id.id,
        'owner_id': stock_lot.owner_id.id,
        'buyer_id': stock_lot.buyer_id.id,
        'error_description': body.description,
        'note': body.product_error_note,
    }

    return {
        'subject': body.subject,
        'branch': branch_id.id,
        'state_id': state_id.id,
        'priority_id': priority_id.id,
        'note_SO': body.delivery_address,
        'department_id': department_id.id,
        'ticket_type_id': ticket_type_id.id,
        'ir_attachment_ids': [(6, 0, attachments.ids)],
        'note': body.product_error_note,
        'ticket_product_ids': [(0, 0, ticket_product_vals)],
        'requestor': customer_id.id,
        'origin_sale_order': body.origin_sale_order,
        'install_address': body.install_address,
        'install_note': body.install_note,
        'technical_solution_attachment_ids': [(6, 0, technical_solution_attachments.ids)],
        'technical_solution_note': body.technical_solution_note,
        'technical_solution_link': body.technical_solution_link,
        'materials_supplier': body.materials_supplier,
        'expected_implementation_date': body.expected_implementation_date,
        'expected_implementation_address': body.expected_implementation_address,
        'implementation_note': body.implementation_note,
    }
