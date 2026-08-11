# -*- coding: utf-8 -*-
import json
import logging
import requests

from odoo import _, api, fields, models
from odoo.addons.dat_sap_config.tools.sap import (
    get_sap_request_body_bool,
    get_sap_request_body_date,
    get_sap_request_body_html,
)
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

EXCLUDED_SAP_REASON_CODES = ("04-994", "04-995")


class SaleOrder(models.Model):
    _inherit = "sale.order"

    ticket_id = fields.Many2one("ticket.helpdesk", string="Ticket", ondelete="cascade")
    wf_external_id = fields.Char(
        string="Workflow External ID",
        related="ticket_id.wf_external_id",
        readonly=True,
        store=True,
    )
    step_external_id = fields.Char(
        string="Step External ID",
        related="ticket_id.step_external_id",
        readonly=True,
        store=True,
    )
    is_exchange_1_1 = fields.Boolean(
        string="Doi 1-1",
        related="ticket_id.is_exchange_1_1",
        readonly=True,
        store=True,
    )
    ticket_name = fields.Char(
        string="Ma yeu cau",
        related="ticket_id.name",
        readonly=True,
        store=True,
        index=True,
    )
    ticket_owner_id = fields.Many2one(
        "res.partner",
        string="Khach hang so huu",
        related="ticket_id.owner_id",
        readonly=True,
        store=True,
        index=True,
    )
    ticket_stock_name = fields.Char(
        string="So seri",
        related="ticket_id.stock_name",
        readonly=True,
        store=True,
        index=True,
    )
    ticket_assigned_user_id = fields.Many2one(
        "res.users",
        string="Nhan vien phu trach",
        related="ticket_id.assigned_user_id",
        readonly=True,
        store=True,
        index=True,
    )
    ticket_saleperson_id = fields.Many2one(
        "hr.employee",
        string="Nhan vien kinh doanh",
        related="ticket_id.saleperson_id",
        readonly=True,
        store=True,
        index=True,
    )
    ticket_saleperson_department_id = fields.Many2one(
        "hr.department",
        string="Phong ban NVKD",
        related="ticket_id.saleperson_deparment_id",
        readonly=True,
    )
    ticket_saleperson_branch_id = fields.Many2one(
        "res.company",
        string="Chi nhanh NVKD",
        related="ticket_id.saleperson_branch",
        readonly=True,
    )
    ticket_saleperson_sap_slp_code = fields.Integer(
        string="Salesperson SAP Slp Code",
        related="ticket_id.saleperson_sap_slp_code",
        readonly=True,
    )
    ticket_saleperson_sap_business_area = fields.Char(
        string="Salesperson SAP Business Area",
        related="ticket_id.saleperson_sap_business_area",
        readonly=True,
    )
    sap_issue_branch_id = fields.Many2one(
        "res.company",
        string="Chi nhánh xuất SAP",
        compute="_compute_sap_issue_branch_id",
        store=True,
        readonly=False,
        copy=False,
        help="Chi nhánh dùng để gửi U_Store/U_InvStore sang SAP. Hệ thống tự gợi ý, Sales có thể chọn lại trước khi tạo SO/ĐXVT.",
    )

    sap_is_issue_invoice = fields.Selection(
        string="Is Issue Invoice",
        selection=[
            ("Y", "PHHĐ ngay"),
            ("N", "Không lấy hóa đơn"),
            ("A", "PHHĐ sau"),
            ("B", "Giá có VAT - không PHHĐ"),
            ("T", "PHHĐ sau bằng tay"),
            ("C", "PHHĐ ngay bằng tay"),
        ],
        default="N",
    )
    sap_is_install = fields.Boolean(
        string="Is Install",
        compute="_compute_install_and_setup_and_voucher",
        store=True,
    )
    sap_is_cocq = fields.Boolean(string="Is COCQ", default=False)
    sap_is_setup = fields.Boolean(
        string="Is Setup",
        compute="_compute_install_and_setup_and_voucher",
        store=True,
    )
    sap_voucher_type = fields.Selection(
        string="Voucher Type",
        selection=[
            ("1350", "BH-03E Dispatch For Repair"),
            ("1360", "BH-03F Dispatch For Warranty"),
        ],
        default="1350",
    )
    # Có tạo SO bên SAP hay không
    sap_is_create_so = fields.Boolean(
        string="Tạo SO bên SAP",
        default=False,
        help="Mặc định không tạo SO bên SAP. Chỉ khi tích vào mới cho phép tạo chứng từ trên SAP."
    )

    # === Lý do SAP ===
    sap_reason_id = fields.Many2one(
        "sap.voucher.reason",
        string="Lý do chứng từ",
        domain="[('voucher_type', '=', sap_voucher_type), ('active', '=', True), ('code', 'not in', ['04-994', '04-995'])]",
    )
    sap_tax_code = fields.Char(string="SAP Tax Code", default="SVN3")

    create_by = fields.Many2one(
        "res.users",
        string="Ng\u01b0\u1eddi t\u1ea1o",
        readonly=True,
        default=lambda self: self.env.user,
    )
    sap_status = fields.Char(
        string="SAP Status",
        readonly=True,
        help="Status of the Sale Order in SAP",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        store=True,
        readonly=False,
        precompute=True,
    )
    filler_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Filler Warehouse",
        store=True,
        readonly=False,
        precompute=True,
    )
    warehouse_domain_ids = fields.Many2many(
        "stock.warehouse",
        string="Warehouse Domain",
        compute="_compute_warehouse_domain",
        store=False,
    )

    address2 = fields.Char(string="Địa chỉ giao hàng")
    document_note = fields.Text(string="Ghi chú chứng từ")

    sap_status = fields.Char(
        string="SAP Status",
        readonly=True,
        help="Status of the Sale Order in SAP",
    )

    # Đã tạo SO trên SAP hay chưa (dựa trên sap_status/docnum)
    sap_is_created_so = fields.Boolean(
        string="Đã tạo SO SAP",
        compute="_compute_sap_is_created_so",
        store=True,
    )

    @api.depends("sap_status")
    def _compute_sap_is_created_so(self):
        for order in self:
            order.sap_is_created_so = bool(order.sap_status)

    @api.depends(
        "ticket_id",
        "ticket_id.saleperson_id",
        "ticket_id.branch",
        "partner_id",
        "warehouse_id",
        "filler_warehouse_id",
    )
    def _compute_sap_issue_branch_id(self):
        for order in self:
            if order.sap_issue_branch_id:
                continue
            branch = order._get_default_sap_issue_branch()
            order.sap_issue_branch_id = branch

    def init(self):
        super_init = getattr(super(), "init", None)
        if super_init:
            super_init()
        excluded_codes = tuple(EXCLUDED_SAP_REASON_CODES)
        self.env.cr.execute("""
            UPDATE sale_order so
               SET sap_reason_id = (
                    SELECT id
                      FROM sap_voucher_reason new_reason
                     WHERE new_reason.voucher_type = so.sap_voucher_type
                       AND new_reason.active IS TRUE
                       AND new_reason.code NOT IN %s
                     ORDER BY new_reason.id
                     LIMIT 1
               )
              FROM sap_voucher_reason old_reason
             WHERE so.sap_reason_id = old_reason.id
               AND (
                    old_reason.active IS NOT TRUE
                    OR old_reason.code IN %s
                    OR old_reason.voucher_type IS DISTINCT FROM so.sap_voucher_type
               )
               AND EXISTS (
                    SELECT 1
                      FROM sap_voucher_reason new_reason
                     WHERE new_reason.voucher_type = so.sap_voucher_type
                       AND new_reason.active IS TRUE
                       AND new_reason.code NOT IN %s
               )
        """, (excluded_codes, excluded_codes, excluded_codes))
        self.env.cr.execute("""
            UPDATE ticket_helpdesk ticket
               SET sap_reason_id = (
                    SELECT id
                      FROM sap_voucher_reason new_reason
                     WHERE new_reason.voucher_type = ticket.sap_voucher_type
                       AND new_reason.active IS TRUE
                       AND new_reason.code NOT IN %s
                     ORDER BY new_reason.id
                     LIMIT 1
               )
              FROM sap_voucher_reason old_reason
             WHERE ticket.sap_reason_id = old_reason.id
               AND (
                    old_reason.active IS NOT TRUE
                    OR old_reason.code IN %s
                    OR old_reason.voucher_type IS DISTINCT FROM ticket.sap_voucher_type
               )
               AND EXISTS (
                    SELECT 1
                      FROM sap_voucher_reason new_reason
                     WHERE new_reason.voucher_type = ticket.sap_voucher_type
                       AND new_reason.active IS TRUE
                       AND new_reason.code NOT IN %s
               )
        """, (excluded_codes, excluded_codes, excluded_codes))

    # -------------------------------------------------------------------------
    # Warehouse helpers
    # -------------------------------------------------------------------------
    @api.depends("ticket_id", "partner_id", "ticket_id.owner_id", "ticket_id.customer_id", "ticket_id.stock_lot_id")
    def _compute_warehouse_domain(self):
        for rec in self:
            rec.warehouse_domain_ids = False
            if not rec.ticket_id:
                continue

            prefixes = []
            ticket = rec.ticket_id.sudo()
            for company in (ticket.branch, rec._get_customer_store_company_for_sap()):
                prefix = ((company.prefix or "") if company else "").strip()
                if prefix and prefix not in prefixes:
                    prefixes.append(prefix)

            warehouses = self.env["stock.warehouse"]
            for prefix in prefixes:
                warehouses |= self.env["stock.warehouse"].search(
                    [("code", "ilike", prefix)]
                )
            rec.warehouse_domain_ids = [(6, 0, warehouses.ids)]

    @api.model
    def _get_default_warehouse(self):
        ticket_id = self._context.get("default_ticket_id")
        if not ticket_id:
            return False

        ticket = self.env["ticket.helpdesk"].sudo().browse(ticket_id)
        if not ticket:
            return False

        prefix = (ticket.branch.prefix or "").strip()
        suffix = "01" if ticket.warranty_service_type == "replace" else "20"
        pattern = f"{prefix}%{suffix}"

        warehouse = self.env["stock.warehouse"].search(
            [("code", "=ilike", pattern)], limit=1
        )
        return warehouse.id or False

    @api.model
    def _get_default_filler_warehouse(self):
        # chỉ dùng khi cần, hiện tại không dùng default nữa
        return False

    # -------------------------------------------------------------------------
    # Compute install/setup + voucher type
    # -------------------------------------------------------------------------
    @api.depends(
        "ticket_id.service_action",
        "ticket_id.product_warranty_status",
        "ticket_id.request_type",
    )
    def _compute_install_and_setup_and_voucher(self):
        """
        - sap_is_install = True nếu service_action là online/onsite support
        - sap_is_setup = ngược lại
        """
        for order in self:
            ticket = order.ticket_id.sudo() if order.ticket_id else False
            action = ticket.service_action or ""
            is_install = action in (
                "online_technical_support",
                "onsite_technical_support",
            )
            order.sap_is_install = is_install
            order.sap_is_setup = not is_install

    def _get_default_sap_voucher_type_from_ticket(self, ticket):
        action = ticket.service_action or ""
        is_repair = (
            ticket.request_type == "repair"
            or ticket.product_warranty_status in ("out_of_warranty", "not_eligible_for_warranty")
            or action in ("repair_at_dat", "repair_onsite")
        )
        is_warranty = (
            not is_repair
            and ticket.product_warranty_status == "warranty"
            and action in (
                "warranty_at_dat",
                "warranty_onsite",
                "warranty_at_dat_paid",
                "warranty_onsite_paid",
            )
        )
        return "1360" if is_warranty else "1350"

    # -------------------------------------------------------------------------
    # Sync lý do từ SAP
    # -------------------------------------------------------------------------
    def _get_sap_headers_safe(self):
        """Lấy header SAP, tránh lỗi khi model/method chưa sẵn."""
        try:
            return self.env["res.config.settings"].get_sap_headers()
        except Exception as e:
            _logger.error("Không lấy được SAP headers: %s", e)
            raise UserError(
                _(
                    "Không lấy được thông tin kết nối SAP (headers). "
                    "Vui lòng kiểm tra cấu hình SAP."
                )
            )

        # --- gọi /GetResons và sync vào sap.voucher.reason ----------
     # --- gọi /GetResons và sync vào sap.voucher.reason ----------
    def _sync_sap_reasons_for_voucher_type(self, voucher_type=None):
        """Luôn gọi API để lấy lý do theo voucher type."""
        self.ensure_one()
        voucher_type = voucher_type or self.sap_voucher_type
        if not voucher_type:
            return

        ICP = self.env['ir.config_parameter'].sudo()
        api_base_url = (ICP.get_param('dat_sync_sap.sap_api_url') or '').rstrip('/')
        if not api_base_url:
            raise UserError(_("SAP API base URL (dat_sync_sap.sap_api_url) chưa được cấu hình."))

        url = f"{api_base_url}/GetResons"

        # payload GIỐNG Postman: body JSON
        payload = {
            # để nguyên string cho chắc (Postman gửi 1360 cũng ok, nhưng string luôn an toàn)
            "U_VoucherTypeID": voucher_type
        }

        headers = dict(self._get_sap_headers_safe() or {})
        headers.setdefault('Content-Type', 'application/json')

        _logger.info(
            "GetResons request: url=%s, payload=%s, headers(no-auth)=%s, so=%s",
            url,
            payload,
            {k: v for k, v in headers.items() if k.lower() != 'authorization'},
            self.display_name,
        )

        try:
            # QUAN TRỌNG: gửi BODY JSON (json=payload) – KHÔNG dùng params
            response = requests.get(
                url,
                headers=headers,
                json=payload,
                timeout=30,
            )
        except Exception as e:
            _logger.exception("Lỗi khi gọi GetResons: %s", e)
            raise UserError(_("Không kết nối được tới SAP GetResons API: %s") % e)

        _logger.info(
            "GetResons raw response: http_status=%s, text=%s",
            response.status_code,
            response.text[:2000],
        )

        if response.status_code != 200:
            # HTTP lỗi – show nguyên body cho dễ debug
            raise UserError(
                _("Lấy danh sách lý do từ SAP thất bại (HTTP %s): %s")
                % (response.status_code, response.text)
            )

        # Parse JSON body
        try:
            res_json = response.json()
        except Exception as e:
            _logger.exception("Không parse được JSON GetResons: %s", e)
            raise UserError(_("Response từ SAP khi lấy lý do không hợp lệ: %s") % e)

        status = (res_json.get('status') or '').upper()
        msg = res_json.get('msg') or ''
        items = res_json.get('result') or []

        _logger.info(
            "GetResons parsed: status=%s, msg=%s, type(result)=%s, len(result)=%s",
            status,
            msg,
            type(items),
            len(items) if isinstance(items, list) else 'N/A',
        )

        # 1) SAP báo lỗi business (CODE không hợp lệ, v.v.)
        if status != 'TRUE':
            raise UserError(
                _("SAP không trả về danh sách lý do cho loại chứng từ %s.\nThông điệp từ SAP: %s")
                % (voucher_type, msg or _("Không rõ"))
            )

        # 2) status TRUE nhưng không có kết quả
        if not isinstance(items, list) or not items:
            raise UserError(
                _("SAP không trả về danh sách lý do cho loại chứng từ %s (result rỗng).")
                % (voucher_type)
            )

        # 3) Có dữ liệu → sync vào bảng sap.voucher.reason
        Reason = self.env['sap.voucher.reason']

        for it in items:
            code = it.get('Code')
            name = it.get('Name')
            if not code or not name:
                continue

            existing = Reason.search([
                ('code', '=', code),
                ('voucher_type', '=', voucher_type),
            ], limit=1)

            if code in EXCLUDED_SAP_REASON_CODES:
                if existing and existing.active:
                    existing.active = False
                continue

            if existing:
                existing.write({
                    'name': name,
                    'active': True,
                })
            else:
                Reason.create({
                    'code': code,
                    'name': name,
                    'voucher_type': voucher_type,
                })

        _logger.info(
            "Đã sync %s lý do cho voucher_type=%s",
            len(items),
            voucher_type,
        )

        # Nếu SO chưa chọn lý do thì auto gán lý do đầu tiên
        # _sync_all_sap_voucher_reasons() loads every catalog. A reason chosen
        # for the order must only be validated against the order's own voucher
        # type, never against the other catalog currently being synchronized.
        if (
            voucher_type == self.sap_voucher_type
            and self._is_invalid_sap_reason(voucher_type=voucher_type)
        ):
            self.sap_reason_id = False

    def _sync_all_sap_voucher_reasons(self):
        """Sync đủ lý do chứng từ để dropdown khớp SaleOne."""
        self.ensure_one()
        for voucher_type in dict(self._fields["sap_voucher_type"].selection):
            self._sync_sap_reasons_for_voucher_type(voucher_type=voucher_type)

    def _is_invalid_sap_reason(self, reason=False, voucher_type=False):
        reason = reason or self.sap_reason_id
        voucher_type = voucher_type or self.sap_voucher_type
        return bool(
            reason
            and (
                reason.code in EXCLUDED_SAP_REASON_CODES
                or not reason.active
                or (voucher_type and reason.voucher_type != voucher_type)
            )
        )

    def _get_fallback_sap_reason(self, voucher_type=False):
        self.ensure_one()
        voucher_type = voucher_type or self.sap_voucher_type
        if not voucher_type:
            return self.env["sap.voucher.reason"]
        return self.env["sap.voucher.reason"].search([
            ("voucher_type", "=", voucher_type),
            ("active", "=", True),
            ("code", "not in", EXCLUDED_SAP_REASON_CODES),
        ], limit=1)

    def _normalize_sap_reason(self):
        for order in self:
            if not order.sap_voucher_type:
                continue
            if order._is_invalid_sap_reason():
                order.sap_reason_id = False

    # -------------------------------------------------------------------------
    # Onchange: gọi sync khi cần
    # -------------------------------------------------------------------------
    @api.onchange("ticket_id")
    def _onchange_ticket_id_sync_reason(self):
        """
        Khi đổi Ticket:
        - sap_voucher_type sẽ có giá trị mặc định theo ticket nếu chưa chọn
        - sau đó gọi sync lý do.
        """
        for order in self:
            ticket = order.ticket_id.sudo() if order.ticket_id else False
            if ticket and ticket.sap_reason_id and not order._is_invalid_sap_reason(
                reason=ticket.sap_reason_id,
                voucher_type=order.sap_voucher_type or ticket.sap_voucher_type,
            ):
                order.sap_reason_id = ticket.sap_reason_id
            if order.ticket_id and not order.sap_voucher_type:
                order.sap_voucher_type = order._get_default_sap_voucher_type_from_ticket(ticket)
            order._ensure_sap_issue_branch()
            if order.sap_voucher_type:
                order._sync_all_sap_voucher_reasons()
            order._normalize_sap_reason()

    @api.onchange("warehouse_id", "filler_warehouse_id", "partner_id")
    def _onchange_sap_issue_branch_defaults(self):
        for order in self:
            order._ensure_sap_issue_branch()

    @api.onchange("sap_voucher_type")
    def _onchange_sap_voucher_type(self):
        """Khi loại chứng từ đổi thì luôn lấy lý do mới nhất."""
        for order in self:
            if order.sap_reason_id and order.sap_reason_id.voucher_type != order.sap_voucher_type:
                order.sap_reason_id = False
            if order.sap_voucher_type:
                order._sync_all_sap_voucher_reasons()
            order._normalize_sap_reason()

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ticket_id') and not vals.get('sap_voucher_type'):
                ticket = self.env['ticket.helpdesk'].sudo().browse(vals['ticket_id'])
                vals['sap_voucher_type'] = self._get_default_sap_voucher_type_from_ticket(ticket)
            if vals.get('ticket_id') and not vals.get('sap_reason_id'):
                ticket = self.env['ticket.helpdesk'].sudo().browse(vals['ticket_id'])
                voucher_type = vals.get('sap_voucher_type') or ticket.sap_voucher_type
                if (
                    ticket.sap_reason_id
                    and ticket.sap_reason_id.active
                    and ticket.sap_reason_id.code not in EXCLUDED_SAP_REASON_CODES
                    and (not voucher_type or ticket.sap_reason_id.voucher_type == voucher_type)
                ):
                    vals['sap_reason_id'] = ticket.sap_reason_id.id
            if vals.get('ticket_id') and not vals.get('sap_issue_branch_id'):
                draft = self.new(vals)
                branch = draft._get_default_sap_issue_branch()
                if branch:
                    vals['sap_issue_branch_id'] = branch.id
        orders = super().create(vals_list)
        # Log + sync sau khi tạo (cho case tạo bằng code/API)
        for order in orders:
            if order.sap_voucher_type:
                try:
                    order._sync_all_sap_voucher_reasons()
                    order._normalize_sap_reason()
                except Exception as e:
                    # Không chặn create, chỉ log lại – user có thể sync sau
                    _logger.error(
                        "Không sync được lý do SAP cho SO %s khi create: %s",
                        order.name or "NEW",
                        e,
                    )
        if orders and self.env.context.get("from_ticket_helpdesk", False):
            for order in orders:
                order.ticket_id._message_log_batch(
                    bodies={
                        order.ticket_id.id: _('Click On "%s"')
                        % _("Create Quotation")
                    }
                )
                order.ticket_id.is_need_new_so = False
        return orders

    def write(self, vals):
        res = super().write(vals)
        if "partner_id" in vals:
            for order in self.filtered("ticket_id"):
                partner = order.partner_id
                if not partner:
                    continue
                order.ticket_id.sudo().write({
                    "owner_id": partner.id,
                    "owner_address": partner.contact_address,
                })
                order.ticket_id.message_post(
                    body=_("Người sở hữu được cập nhật từ SO %s: %s.")
                    % (order.display_name, partner.display_name)
                )
        # Nếu có đổi loại chứng từ thì sync lại
        if "sap_voucher_type" in vals:
            for order in self:
                if order.sap_voucher_type:
                    try:
                        order._sync_all_sap_voucher_reasons()
                        order._normalize_sap_reason()
                    except Exception as e:
                        _logger.error(
                            "Không sync được lý do SAP cho SO %s khi write: %s",
                            order.name,
                            e,
                        )
        if "sap_reason_id" in vals:
            self._normalize_sap_reason()
        return res

    def _validate_exchange_sap_values(self):
        self.ensure_one()
        if not self.is_exchange_1_1:
            return
        if not self.sap_reason_id:
            raise UserError(_("SO đổi 1-1 bắt buộc chọn Lý do SAP trước khi gửi SAP."))
        if self.sap_reason_id.voucher_type != self.sap_voucher_type:
            raise UserError(_("Lý do SAP đã chọn không đúng với loại chứng từ."))

    def _get_sap_issue_invoice_for_payload(self):
        self.ensure_one()
        return "N" if self.is_exchange_1_1 else self.sap_is_issue_invoice

    def _get_sap_tax_code_for_payload(self):
        self.ensure_one()
        return (self.sap_tax_code or "SVN3").strip() if self.is_exchange_1_1 else False

    def _get_salesperson_so_metadata(self, serial_number=False):
        self.ensure_one()
        salesperson = self.ticket_id.sudo().saleperson_id if self.ticket_id else False
        if not salesperson:
            raise UserError(
                _(
                    "API SerialItem không trả về dữ liệu cho serial %(serial)s. "
                    "Vui lòng chọn Nhân viên kinh doanh trong tab Thông tin nhân viên kinh doanh trước khi tạo SO SAP."
                )
                % {"serial": serial_number or ""}
            )

        slp_code = getattr(salesperson, "sap_slp_code", False)
        business_unit = (getattr(salesperson, "sap_business_area", False) or "").strip()
        if slp_code in (None, False, "") or not business_unit:
            raise UserError(
                _(
                    "Nhân viên kinh doanh %(salesperson)s chưa có đủ SAP Slp Code và SAP Business Area "
                    "để thay thế dữ liệu SerialItem cho serial %(serial)s. "
                    "Vui lòng chạy cron SAP: Sync Salesperson Slp/BU (Manual) hoặc cập nhật lại dữ liệu nhân viên."
                )
                % {
                    "salesperson": salesperson.display_name,
                    "serial": serial_number or "",
                }
            )

        _logger.info(
            "SerialItem SO metadata fallback to salesperson: serial=%s so=%s salesperson=%s slp=%s bu=%s",
            serial_number,
            self.display_name,
            salesperson.display_name,
            slp_code,
            business_unit,
        )
        return {
            "SlpCode": slp_code,
            "U_BusinessUnit": business_unit,
        }

    def _get_serial_item_so_metadata(self):
        self.ensure_one()
        ticket = self.ticket_id.sudo() if self.ticket_id else False
        serial_number = (
            ticket.stock_lot_id.name
            if ticket and ticket.stock_lot_id
            else False
        )
        if not serial_number:
            return {}

        ICP = self.env["ir.config_parameter"].sudo()
        api_base_url = (
            ICP.get_param("dat_bnk.bnk_api_url")
            or ICP.get_param("dat_sync_sap.sap_api_url")
            or "https://api-dat.datgroup.com.vn/BnK"
        ).rstrip("/")
        url = "%s/SerialItem" % api_base_url
        payload = {"CardCode": "", "SerialNumber": serial_number}
        headers = dict(self._get_sap_headers_safe() or {})
        headers.setdefault("Content-Type", "application/json")

        _logger.info(
            "SerialItem SO metadata request: url=%s serial=%s so=%s",
            url,
            serial_number,
            self.display_name,
        )
        try:
            response = requests.get(url, headers=headers, json=payload, timeout=30)
        except Exception as e:
            _logger.exception("SerialItem SO metadata request failed for %s: %s", serial_number, e)
            raise UserError(_("Không kết nối được API SerialItem cho serial %s: %s") % (serial_number, e))

        if response.status_code != 200:
            raise UserError(
                _("Lấy SlpCode/U_BusinessUnit từ SerialItem thất bại cho serial %(serial)s (HTTP %(code)s): %(body)s")
                % {
                    "serial": serial_number,
                    "code": response.status_code,
                    "body": response.text,
                }
            )

        try:
            data = response.json() or {}
        except Exception as e:
            raise UserError(_("API SerialItem trả về JSON không hợp lệ cho serial %s: %s") % (serial_number, e))

        items = data.get("result") or []
        if isinstance(items, dict):
            items = items.get("Items") or []
        row = next(
            (item for item in items if item.get("SerialNumber") == serial_number),
            items[0] if items else False,
        )
        if not row:
            return self._get_salesperson_so_metadata(serial_number=serial_number)

        slp_code = row.get("SlpCode")
        business_unit = row.get("U_BusinessUnit")
        if slp_code in (None, False, "") or not business_unit:
            return self._get_salesperson_so_metadata(serial_number=serial_number)
        return {
            "SlpCode": slp_code,
            "U_BusinessUnit": business_unit,
        }

    def _must_create_sap_so_for_immediate_invoice(self):
        self.ensure_one()
        paid_repair_actions = (
            "repair_at_dat",
            "repair_onsite",
            "warranty_at_dat_paid",
            "warranty_onsite_paid",
        )
        return bool(
            self.wf_external_id == "workflow_1"
            and self.ticket_id.sudo().service_action in paid_repair_actions
            and self.sap_is_issue_invoice == "Y"
        )

    @api.onchange("sap_is_issue_invoice", "ticket_id")
    def _onchange_immediate_invoice_create_sap_so(self):
        for order in self:
            if order._must_create_sap_so_for_immediate_invoice():
                order.sap_is_create_so = True

    @api.onchange("filler_warehouse_id")
    def _onchange_filler_warehouse_id_keep_saleone_lines(self):
        for order in self:
            if not order.filler_warehouse_id:
                continue
            for line in order.order_line.filtered(lambda l: not l.display_type and l.filler_warehouse_id != order.filler_warehouse_id):
                line.filler_warehouse_id = order.filler_warehouse_id

    # -------------------------------------------------------------------------
    # SAP payloads
    # -------------------------------------------------------------------------

    def _get_customer_store_company_for_sap(self):
        self.ensure_one()

        partners = self.env["res.partner"]
        ticket = self.ticket_id.sudo() if self.ticket_id else False
        for partner in (
            self.partner_id,
            ticket.owner_id if ticket else False,
            ticket.customer_id if ticket else False,
        ):
            if not partner:
                continue
            partners |= partner
            commercial_partner = partner.commercial_partner_id
            if commercial_partner:
                partners |= commercial_partner

        for partner in partners:
            sale_person = getattr(partner.sudo(), "sale_person", False)
            company = sale_person.company_id if sale_person else False
            if company:
                return company

        lot = ticket.stock_lot_id if ticket else False
        sale_person = getattr(lot.sudo(), "saleperson_id", False) if lot else False
        if sale_person and sale_person.company_id:
            return sale_person.company_id

        return False

    def _get_store_company_from_serial_item_metadata(self, serial_item_metadata=None):
        self.ensure_one()
        slp_code = (serial_item_metadata or {}).get("SlpCode")
        if slp_code in (None, False, ""):
            return False
        salesperson = self.env["hr.employee"].sudo().search(
            [("sap_slp_code", "=", slp_code)],
            limit=1,
        )
        return salesperson.company_id if salesperson else False

    def _get_default_sap_issue_branch(self, serial_item_metadata=None):
        self.ensure_one()
        ticket = self.ticket_id.sudo() if self.ticket_id else False
        return (
            self.sap_issue_branch_id
            or self._get_store_company_from_serial_item_metadata(serial_item_metadata)
            or (ticket and ticket.saleperson_id and ticket.saleperson_id.company_id)
            or (self.ticket_saleperson_id and self.ticket_saleperson_id.company_id)
            or (ticket and ticket.saleperson_branch)
            or self._get_customer_store_company_for_sap()
            or (ticket and ticket.branch)
            or (self.warehouse_id and self.warehouse_id.company_id)
            or (self.filler_warehouse_id and self.filler_warehouse_id.company_id)
            or self.company_id
        )

    def _get_company_store_code_for_sap(self, company):
        if not company:
            return 1
        name = (company.name or "").lower()
        prefix = (getattr(company, "prefix", "") or "").upper().strip()
        if "ho chi minh" in name or prefix.startswith("HCM"):
            return 1
        if "can tho" in name or prefix.startswith("CTH") or prefix.startswith("CT"):
            return 2
        if "ha noi" in name or prefix.startswith("HNI") or prefix.startswith("HN"):
            return 3
        return 1

    def _ensure_sap_issue_branch(self, serial_item_metadata=None):
        for order in self:
            if order.sap_issue_branch_id:
                continue
            branch = order._get_default_sap_issue_branch(serial_item_metadata=serial_item_metadata)
            if branch:
                order.sap_issue_branch_id = branch

    def _compute_store_for_sap(self, serial_item_metadata=None):
        """
        Tính U_Store để gửi sang SAP, map theo chi nhánh:
          1 = HCM
          2 = Cần Thơ
          3 = Hà Nội

        Ưu tiên:
          - ticket_id.branch
          - company_id
          - warehouse_id.company_id

        Fallback: 1 nếu không xác định được (cho chắc dùng HCM).
        """
        self.ensure_one()
        company = self._get_default_sap_issue_branch(serial_item_metadata=serial_item_metadata)
        return self._get_company_store_code_for_sap(company)

        ticket = self.ticket_id.sudo() if self.ticket_id else False

        company = (
            self._get_store_company_from_serial_item_metadata(serial_item_metadata)
            or (ticket and ticket.saleperson_id and ticket.saleperson_id.company_id)
            or (self.ticket_saleperson_id and self.ticket_saleperson_id.company_id)
            or (ticket and ticket.saleperson_branch)
            or self._get_customer_store_company_for_sap()
            or (ticket and ticket.branch)
            or (self.warehouse_id and self.warehouse_id.company_id)
            or (self.filler_warehouse_id and self.filler_warehouse_id.company_id)
            or self.company_id
        )

        if not company:
            return 1

        name = (company.name or "").lower()
        prefix = (getattr(company, "prefix", "") or "").upper().strip()

        # --- HCM ---
        if (
            "hồ chí minh" in name
            or "ho chi minh" in name
            or prefix.startswith("HCM")
        ):
            return 1

        # --- Cần Thơ ---
        if (
            "cần thơ" in name
            or "can tho" in name
            or prefix.startswith("CTH")
            or prefix.startswith("CT")
        ):
            return 2

        # --- Hà Nội ---
        if (
            "hà nội" in name
            or "ha noi" in name
            or prefix.startswith("HNI")
            or prefix.startswith("HN")
        ):
            return 3

        # Không đoán được thì default HCM
        return 1


    def _get_line_item_code_for_sap(self, line):
        return (
            line.product_template_id.default_code
            or line.product_id.default_code
            or ""
        ).strip()

    def _get_line_source_warehouse_code_for_sap(self, line):
        return (
            (line.filler_warehouse_id.code or "")
            or (self.filler_warehouse_id.code or "")
        ).strip()

    def _is_dxvt_inventory_line(self, line):
        product_type = getattr(line.product_id, "detailed_type", False) or getattr(line.product_id, "type", False)
        return bool(line.product_id and product_type != "service")

    def _get_dxvt_selected_lines(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: not l.display_type and l.create_sap and self._is_dxvt_inventory_line(l)
        )

    def _move_dxvt_lines_to_target_warehouse(self):
        """Use the DXVT destination warehouse as the source warehouse for SAP SO."""
        self.ensure_one()
        lines = self._get_dxvt_selected_lines()
        if not lines:
            return self.env['sale.order.line']

        target_code = self._get_dxvt_target_warehouse_code()
        target_warehouse = self.env['stock.warehouse'].search(
            [('code', '=', target_code)],
            limit=1,
        )
        if not target_warehouse:
            raise UserError(
                _("Không tìm thấy kho đích ĐXVT có mã %s trong Odoo.") % target_code
            )

        lines.write({
            'filler_warehouse_id': target_warehouse.id,
            'sap_dxvt_created': True,
        })
        _logger.info(
            "[DXVT][MOVE_LINES] so=%s line_ids=%s target_warehouse=%s",
            self.name,
            lines.ids,
            target_warehouse.code,
        )
        return lines

    def _looks_like_sap_warehouse_code(self, code):
        code = (code or "").strip()
        if not code or " " in code:
            return False
        return any(ch.isdigit() for ch in code) and any(ch.isalpha() for ch in code)

    def _get_dxvt_target_warehouse_code(self):
        self.ensure_one()

        # Ưu tiên Kho vật tư ở header vì đây mới là kho service đích trên màn hình hiện tại.
        candidates = [
            (self.warehouse_id.code or "").strip(),
            (self.filler_warehouse_id.code or "").strip(),
        ]
        for code in candidates:
            if self._looks_like_sap_warehouse_code(code):
                return code

        # Fallback: suy ra theo chi nhánh + loại xử lý.
        store_company = (
            self._get_customer_store_company_for_sap()
            or (self.ticket_id and self.ticket_id.sudo().branch)
        )
        prefix = ((store_company.prefix or "") if store_company else "").strip()
        ticket = self.ticket_id.sudo() if self.ticket_id else False
        suffix = "01" if (ticket and ticket.warranty_service_type == "replace") else "20"
        if prefix:
            wh = self.env["stock.warehouse"].search([
                ("code", "ilike", f"{prefix}%"),
            ])
            wh = wh.filtered(lambda w, s=suffix: (w.code or "").upper().endswith(s))[:1]
            if wh and wh.code:
                return wh.code.strip()

        # Fallback cuối cùng để vẫn có dữ liệu debug.
        return ((self.warehouse_id.code or "").strip() or (self.filler_warehouse_id.code or "").strip())

    def _validate_dxvt_payload_inputs(self):
        self.ensure_one()

        selected_lines = self._get_dxvt_selected_lines()
        if not selected_lines:
            raise UserError(_("Vui lòng tích 'Tạo SAP' cho ít nhất một dòng vật tư."))

        source_codes = []
        line_debug = []

        for line in selected_lines:
            item_code = self._get_line_item_code_for_sap(line)
            source_code = self._get_line_source_warehouse_code_for_sap(line)
            qty = line.product_uom_qty or 0.0

            line_debug.append(
                {
                    "line_id": line.id,
                    "product": line.product_id.display_name,
                    "item_code": item_code,
                    "qty": qty,
                    "source_wh": source_code,
                }
            )

            if not item_code:
                raise UserError(
                    _("Dòng '%s' chưa có mã SAP (default_code).")
                    % (line.product_id.display_name or line.name or line.id)
                )

            if qty <= 0:
                raise UserError(
                    _("Dòng '%s' có số lượng không hợp lệ: %s.")
                    % (line.product_id.display_name or line.name or line.id, qty)
                )

            if not source_code:
                raise UserError(
                    _("Dòng '%s' chưa có Kho vật tư.")
                    % (line.product_id.display_name or line.name or line.id)
                )

            source_codes.append(source_code)

        unique_source_codes = sorted(set(source_codes))
        target_code = self._get_dxvt_target_warehouse_code()

        if not target_code:
            raise UserError(_("Chưa có Kho Service trên đơn hàng."))

        if len(unique_source_codes) > 1:
            raise UserError(
                _(
                    "ĐXVT hiện chỉ hỗ trợ 1 kho nguồn cho mỗi lần tạo. "
                    "Đơn %s đang có nhiều kho nguồn: %s. "
                    "Vui lòng tách các dòng theo từng kho rồi tạo riêng."
                )
                % (self.name, ", ".join(unique_source_codes))
            )

        filler_code = unique_source_codes[0]

        return {
            "filler_code": filler_code,
            "target_code": target_code,
            "line_debug": line_debug,
        }

    def _get_dxvt_skip_reason(self):
        self.ensure_one()

        selected_lines = self._get_dxvt_selected_lines()
        if not selected_lines:
            return _("Không có dòng vật tư cần xuất kho nội bộ để tạo ĐXVT.")

        dxvt_info = self._validate_dxvt_payload_inputs()
        filler_code = (dxvt_info.get("filler_code") or "").strip().upper()
        target_code = (dxvt_info.get("target_code") or "").strip().upper()
        if filler_code and target_code and filler_code == target_code:
            return _(
                "Bỏ qua tạo ĐXVT vì Kho nguồn (%s) đang trùng Kho Service (%s). "
                "Luồng này được xử lý như xuất trực tiếp từ kho ra khách."
            ) % (dxvt_info["filler_code"], dxvt_info["target_code"])
        return False


    def prepare_sap_so_lines(self):
        self.ensure_one()
        tax_code = self._get_sap_tax_code_for_payload()
        lines = []
        for line in self.order_line:
            line_payload = {
                    "ItemCode": self._get_line_item_code_for_sap(line),
                    "Quantity": line.product_uom_qty,
                    "Price": line.price_unit - line.sap_discount_amount,
                    "WhsCode": self._get_line_source_warehouse_code_for_sap(line),
                    "U_isDiscount": line.sap_is_discount,
                    "U_WarrTime": line.sap_wmonth or 0,
                    "U_OrigiDiscPrcnt": line.discount or 0,
                    "U_OrigiPrice": line.price_unit or 0,
                    "U_DiscAmt": line.sap_discount_amount or 0,
                }
            if tax_code:
                line_payload["TaxCode"] = tax_code
            lines.append(line_payload)
        return lines

    def prepare_sap_so_payload(self):
        self.ensure_one()
        self._normalize_sap_reason()
        self._validate_exchange_sap_values()
        return self._prepare_sap_so_batch_payload()

        serial_item_metadata = self._get_serial_item_so_metadata()
        # Ghi chú cho kho lấy từ note
        warehouse_note = get_sap_request_body_html(self.note or "").strip()
        # Ghi chú chứng từ (toàn cục) lấy từ document_note
        document_note = get_sap_request_body_html(
            self.document_note
            or (self.ticket_id.sudo()._build_document_note() if self.ticket_id else "")
        ).strip()
        payload = {
            "CardCode": self.partner_id.card_code or "",
            "PostingDate": get_sap_request_body_date(fields.Date.context_today(self)),
            "DocDueDate": get_sap_request_body_date(
                self.commitment_date or self.expected_date
            ),
            "TaxDate": get_sap_request_body_date(fields.Date.context_today(self)),
            # Comment hiển thị trên chứng từ SAP
            "Comments": document_note,
            "U_IsIssueInvoice": self._get_sap_issue_invoice_for_payload() or "N",
            "U_isInstall": get_sap_request_body_bool(self.sap_is_install),
            "U_IsCOCQ": get_sap_request_body_bool(self.sap_is_cocq),
            "U_IsSetup": get_sap_request_body_bool(self.sap_is_setup),
            "Address2": (self.address2 or "").strip(),
            "U_VoucherTypeID": self.sap_voucher_type,
            "U_Store": self._compute_store_for_sap(serial_item_metadata=serial_item_metadata),
            # Ghi chú chung
            "U_NoteForAll": document_note,
            # Ghi chú cho kho
            "U_NoteForWhs": warehouse_note,
            "Lines": self.prepare_sap_so_lines(),
        }
        # Nếu SAP yêu cầu truyền thêm mã lý do:
        payload.update(serial_item_metadata)
        payload["U_Reasons"] = self.sap_reason_id.code if self.sap_reason_id else ""
        return payload


    def prepare_sap_dxvt_lines(self):
        self.ensure_one()

        # Chỉ lấy các dòng được tích "Tạo SAP"
        selected_lines = self._get_dxvt_selected_lines()

        # Nếu muốn bắt buộc chọn ít nhất 1 dòng thì thêm check này
        if not selected_lines:
            raise UserError(_("Vui lòng tích 'Tạo SAP' cho ít nhất một dòng vật tư."))
        lines = []
        for line in selected_lines:
            lines.append(
                {
                    "ItemCode": self._get_line_item_code_for_sap(line),
                    "Quantity": line.product_uom_qty,
                    "WhsCode": self._get_line_source_warehouse_code_for_sap(line),
                }
            )
        return lines

    def prepare_sap_dxvt_payload(self):
        ticket = self.ticket_id.sudo() if self.ticket_id else False
        action = ticket.service_action or ""
        is_warranty = action in (
            "warranty_at_dat",
            "warranty_onsite",
            "warranty_at_dat_paid",
            "warranty_onsite_paid",
        )
        u_voucher_type_id = "3130" if is_warranty else "3140"
        self._ensure_sap_issue_branch()
        store_value = self._compute_store_for_sap()
        warehouse_note = get_sap_request_body_html(self.note or "").strip()
        document_note = get_sap_request_body_html(
            self.document_note
            or (ticket._build_document_note() if ticket else "")
        ).strip()

        dxvt_info = self._validate_dxvt_payload_inputs()
        card_code = (self.partner_id.card_code or "").strip()
        if not card_code:
            raise UserError(
                _("Khách hàng trên SO chưa có CardCode nên không thể tạo ĐXVT.")
            )
        payload = {
            "CardCode": card_code,
            "PostingDate": get_sap_request_body_date(fields.Date.context_today(self)),
            "DocDueDate": get_sap_request_body_date(
                self.commitment_date or self.expected_date
            ),
            "Filler": dxvt_info["filler_code"],
            "ToWhsCode": dxvt_info["target_code"],
            "TaxDate": get_sap_request_body_date(fields.Date.context_today(self)),
            "Comments": document_note,
            "U_VoucherTypeID": u_voucher_type_id,
            "U_Store": store_value,
            "U_NoteForAll": document_note,
            "U_NoteForWhs": warehouse_note,
            "Items": self.prepare_sap_dxvt_lines(),
        }

        _logger.info(
            "[DXVT][PAYLOAD] so=%s payload=%s",
            self.name,
            json.dumps(payload, ensure_ascii=False),
        )
        return payload



    def _safe_json_dumps_for_log(self, value):
        try:
            return json.dumps(value or {}, ensure_ascii=False, indent=2, default=str)
        except Exception:
            return str(value)

    def _mask_sap_headers_for_log(self, headers):
        masked = dict(headers or {})
        for key in list(masked.keys()):
            if str(key).lower() in ("authorization", "x-api-key", "apikey", "api-key", "token"):
                masked[key] = "***"
        return masked

    def _post_sap_debug_message(self, title, payload):
        self.ensure_one()
        try:
            body = "<b>%s</b><pre>%s</pre>" % (title, self._safe_json_dumps_for_log(payload))
            self.message_post(body=body)
        except Exception:
            _logger.exception("[SAP][DEBUG][CHATTER][FAILED] so=%s title=%s", self.name, title)

    def _log_sap_exchange(self, stage, data):
        self.ensure_one()
        _logger.info("[SAP][%s] so=%s\n%s", stage, self.name, self._safe_json_dumps_for_log(data))


    def create_sap_doc(self, doc_type="SO"):
        self.ensure_one()

        header = self._get_sap_headers_safe()
        api_link = "/CreateSOForWarrFix"
        json_data = {}
        confirmation_values = {}

        if doc_type == "SO":
            # Luôn chuẩn bị giá trị xác nhận (qua bước tiếp theo) trước
            confirmation_values = self._prepare_confirmation_values()

            # Backfill quotations whose ticket already has a DXVT number but
            # whose lines still point to the original source warehouse.
            if self.ticket_id and (self.ticket_id.sap_dxvt_order_number or '').strip():
                self._move_dxvt_lines_to_target_warehouse()

            if self._must_create_sap_so_for_immediate_invoice() and not self.sap_is_create_so:
                self.sap_is_create_so = True

            # Nếu KHÔNG tích "Tạo SO bên SAP" thì dừng tại đây:
            # => Odoo qua bước tiếp theo, nhưng không gọi SAP
            if not self.sap_is_create_so:
                self.write(confirmation_values)
                return False

            # Nếu có tích thì mới chuẩn bị payload và gọi SAP
            self._normalize_sap_reason()
            json_data = self.prepare_sap_so_payload()

        elif doc_type == "DXVT":
            api_link = "/CreateITRForWarrFix"
            skip_reason = self._get_dxvt_skip_reason()
            if skip_reason:
                _logger.info(
                    "[DXVT][SKIP] so=%s reason=%s",
                    self.name,
                    skip_reason,
                )
                self._post_sap_debug_message("DXVT SKIPPED", {
                    "reason": skip_reason,
                })
                return False
            json_data = self.prepare_sap_dxvt_payload()
            _logger.info(
                "[DXVT][REQUEST] so=%s api=%s payload=%s",
                self.name,
                api_link,
                json.dumps(json_data, ensure_ascii=False),
            )

        api_base_url = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("dat_sync_sap.sap_api_url")
        )
        full_api_url = f"{api_base_url}{api_link}"

        request_debug = {
            "doc_type": doc_type,
            "url": full_api_url,
            "headers": self._mask_sap_headers_for_log(header),
            "payload": json_data,
        }
        self._log_sap_exchange("REQUEST", request_debug)

        try:
            response = requests.post(full_api_url, headers=header, json=json_data)
        except Exception as exc:
            error_debug = {
                "doc_type": doc_type,
                "url": full_api_url,
                "payload": json_data,
                "error": str(exc),
            }
            self._log_sap_exchange("HTTP_ERROR", error_debug)
            if doc_type == "DXVT":
                self._post_sap_debug_message("DXVT HTTP ERROR", error_debug)
            raise UserError(_("Lỗi gọi SAP %s: %s") % (doc_type, exc))

        response_text = response.text
        response_debug = {
            "doc_type": doc_type,
            "url": full_api_url,
            "status_code": response.status_code,
            "reason": response.reason,
            "text": response_text,
        }
        self._log_sap_exchange("RESPONSE_RAW", response_debug)

        if response.status_code != 200:
            if doc_type == "DXVT":
                self._post_sap_debug_message("DXVT RESPONSE ERROR", {
                    "request": request_debug,
                    "response": response_debug,
                })
            raise UserError(
                _("Failed to create new %s in SAP: %s")
                % (doc_type, response.reason)
            )

        try:
            res_json = response.json()
        except Exception:
            parse_debug = {
                "doc_type": doc_type,
                "url": full_api_url,
                "response_text": response_text,
            }
            self._log_sap_exchange("RESPONSE_JSON_PARSE_ERROR", parse_debug)
            if doc_type == "DXVT":
                self._post_sap_debug_message("DXVT JSON PARSE ERROR", {
                    "request": request_debug,
                    "response": response_debug,
                })
            raise UserError(_("SAP trả về dữ liệu không phải JSON cho %s") % doc_type)

        self._log_sap_exchange("RESPONSE_JSON", {
            "doc_type": doc_type,
            "url": full_api_url,
            "json": res_json,
        })

        sap_success, docnumber, sap_message = self._parse_sap_create_response(res_json)

        if sap_success:

            # CHỈ lưu trạng thái SAP khi là SO
            if doc_type == "SO" and docnumber:
                # Lưu DocNum vào trạng thái SAP
                vals = dict(confirmation_values or {})
                vals.update({
                    "sap_status": docnumber,
                    "name": docnumber,
                })
                self.write(vals)
                # Nếu muốn, gán luôn số chứng từ SAP cho tên
            elif doc_type == "SO":
                raise UserError(_("SAP trả về thành công nhưng không có số SO. Response: %s") % res_json)

            if doc_type == "DXVT" and not docnumber:
                self._post_sap_debug_message("DXVT SUCCESS WITHOUT DOCNUMBER", {
                    "request": request_debug,
                    "response": res_json,
                })
                raise UserError(_("SAP trả về thành công nhưng không có số ĐXVT. Response: %s") % res_json)

            if doc_type == "DXVT":
                self._post_sap_debug_message("DXVT SUCCESS", {
                    "request": request_debug,
                    "response": res_json,
                })
                self._move_dxvt_lines_to_target_warehouse()

            return docnumber
        else:
            if doc_type == "DXVT":
                error_debug = {
                    "request": request_debug,
                    "response": res_json,
                    "filler": json_data.get("Filler", ""),
                    "to_whs": json_data.get("ToWhsCode", ""),
                    "items": json_data.get("Items", []),
                }
                self._post_sap_debug_message("DXVT FAILED", error_debug)
                raise UserError(
                    _(
                        "Lỗi khi tạo DXVT mới tại SAP: %s\n"
                        "Kho nguồn: %s | Kho đích: %s\n"
                        "API: %s\n"
                        "JSON gửi:\n%s\n"
                        "Phản hồi SAP:\n%s"
                    )
                    % (
                        sap_message,
                        json_data.get("Filler", ""),
                        json_data.get("ToWhsCode", ""),
                        full_api_url,
                        self._safe_json_dumps_for_log(json_data),
                        self._safe_json_dumps_for_log(res_json),
                    )
                )
            raise UserError(
                _("Failed to create new %s in SAP: %s")
                % (doc_type, sap_message)
            )

    def _parse_sap_create_response(self, response_data):
        if isinstance(response_data, list):
            if not response_data:
                return False, False, _("SAP trả về danh sách rỗng.")
            parsed_items = [self._parse_sap_create_response(item) for item in response_data]
            failed_items = [item for item in parsed_items if not item[0]]
            if failed_items:
                return False, False, "; ".join(item[2] for item in failed_items if item[2])
            docnumber = next((item[1] for item in parsed_items if item[1]), False)
            return True, docnumber, "; ".join(item[2] for item in parsed_items if item[2])

        if not isinstance(response_data, dict):
            return False, False, _("SAP trả về dữ liệu không hợp lệ: %s") % response_data

        status = str(response_data.get("status", "")).strip().lower()
        docnumber = response_data.get("docnumber") or response_data.get("DocNum")
        message = (
            response_data.get("msg")
            or response_data.get("message")
            or response_data.get("error")
            or response_data.get("errorMessage")
            or ""
        )

        if isinstance(docnumber, str):
            docnumber_text = docnumber.strip().lower()
            failed_markers = (
                "'status': 'false'",
                '"status": "false"',
                '"status":"false"',
                "status=false",
                "không tìm thấy khách hàng",
                "khong tim thay khach hang",
            )
            if any(marker in docnumber_text for marker in failed_markers):
                return False, False, message or docnumber

        if status in ("true", "success", "succeeded", "ok", "1"):
            if isinstance(docnumber, (dict, list)):
                return False, False, message or _("SAP trả về docnumber không hợp lệ: %s") % docnumber
            return True, docnumber, message
        if status in ("false", "fail", "failed", "error", "0"):
            return False, False, message or _("SAP trả về trạng thái thất bại.")
        if docnumber:
            return True, docnumber, message
        return False, False, message or _("SAP không trả về trạng thái thành công.")

    # -------------------------------------------------------------------------
    # ACTION 1: Tạo SO SAP từng đơn (mỗi báo giá 1 SO riêng)
    # -------------------------------------------------------------------------
    def action_create_sap_so_single(self):
        for order in self:
            if order.wf_external_id == 'workflow_1':
                order.create_sap_doc(doc_type='SO')
        return False  # hoặc chỉ 'return'



    # -------------------------------------------------------------------------
    # ACTION 2: Gộp nhiều báo giá thành 1 SO SAP
    # -------------------------------------------------------------------------
    def action_duplicate_techservice_so(self):
        self.ensure_one()
        seq_date = (
            fields.Datetime.context_timestamp(
                self, fields.Datetime.to_datetime(self.date_order)
            )
            if self.date_order
            else None
        )
        sequence_env = self.with_company(self.company_id).env["ir.sequence"]
        new_name = sequence_env.next_by_code(
            "sale.order", sequence_date=seq_date
        ) or _("New")
        default_vals = {
            "name": new_name,
            "state": "draft",
            "status": "draft",
            "sap_status": False,
            "sap_is_create_so": False,
            "cancel_reason": False,
            "reject_reason": False,
            "origin": self.name,
            "client_order_ref": _("%s - Nhân bản") % (self.name or ""),
        }
        if "ts_pair_origin_order_id" in self._fields:
            default_vals["ts_pair_origin_order_id"] = False
        if "ts_pair_role" in self._fields:
            default_vals["ts_pair_role"] = "primary"
        if "ts_bound_stage" in self._fields:
            default_vals["ts_bound_stage"] = "normal"
        if "ts_price_impact_review_required" in self._fields:
            default_vals["ts_price_impact_review_required"] = False
        if "ts_last_price_change_at" in self._fields:
            default_vals["ts_last_price_change_at"] = False
        if "ts_last_price_change_note" in self._fields:
            default_vals["ts_last_price_change_note"] = False
        for field_name in (
            "ts_main_so_doc_number",
            "ts_main_dxvt_doc_number",
            "ts_lt_so_doc_number",
            "ts_lt_dxvt_doc_number",
            "ts_split_doc_note",
            "ts_split_dxvt_note",
            "ts_split_sap_doc_state",
            "sap_dxvt_order_number",
            "sap_itr_number",
            "sap_dxvt_doc_number",
        ):
            if field_name in self._fields:
                default_vals[field_name] = False

        new_order = self.copy(default_vals)
        new_order.message_post(body=_("Được nhân bản từ SO %s.") % (self.display_name,))
        return {
            "type": "ir.actions.act_window",
            "name": _("Nhân bản SO"),
            "res_model": "sale.order",
            "res_id": new_order.id,
            "view_mode": "form",
            "target": "current",
        }

    def _prepare_sap_so_batch_payload(self):
        """
        Gộp nhiều báo giá thành 1 SO gửi lên SAP.

        Điều kiện:
        - Cùng partner_id
        - Cùng address2 (Địa chỉ giao hàng)
        - Cùng wf_external_id = 'workflow_1'
        - CHỈ lấy các báo giá CHƯA tạo SO trên SAP (chưa có DocNum)
        - Dòng sản phẩm: giữ nguyên từng dòng, KHÔNG gộp số lượng
        """
        # CHỈ lấy các báo giá CHƯA có DocNum (sap_status rỗng)
        self = self.filtered(lambda o: not (o.sap_status or "").strip())
        if not self:
            raise UserError(_("Vui lòng chọn các báo giá CHƯA tạo SO trên SAP."))

        # workflow
        wf_set = set(self.mapped("wf_external_id"))
        if wf_set != {"workflow_1"}:
            raise UserError(_("Chỉ hỗ trợ gộp SO cho workflow_1."))

        # cùng khách hàng
        partners = self.mapped("partner_id")
        if len(partners) != 1:
            raise UserError(_("Các báo giá được gộp phải cùng một Khách hàng."))

        # cùng địa chỉ giao hàng
        addr_set = {(self[0].address2 or "").strip()}
        if len(addr_set) != 1:
            raise UserError(
                _("Các báo giá được gộp phải cùng một 'Địa chỉ giao hàng'.")
            )
        address2 = list(addr_set)[0]

        # cùng loại chứng từ
        voucher_set = set(self.mapped("sap_voucher_type"))
        if len(voucher_set) != 1:
            raise UserError(_("Các báo giá được gộp phải cùng một Loại chứng từ."))
        sap_voucher_type = list(voucher_set)[0]

        # cùng lý do
        self._normalize_sap_reason()
        reason_set = set(self.mapped(lambda o: o.sap_reason_id.id))
        if len(reason_set) != 1:
            raise UserError(_("Các báo giá được gộp phải cùng một Lý do chứng từ."))
        sap_reason = self[0].sap_reason_id

        main = self[0]
        for order in self:
            order._validate_exchange_sap_values()
        serial_item_metadata = [order._get_serial_item_so_metadata() for order in self]
        if any(serial_item_metadata) and not all(serial_item_metadata):
            raise UserError(_("Các SO gộp phải cùng có dữ liệu SlpCode/U_BusinessUnit theo serial."))
        metadata_keys = {
            (metadata.get("SlpCode"), metadata.get("U_BusinessUnit"))
            for metadata in serial_item_metadata
            if metadata
        }
        if len(metadata_keys) > 1:
            raise UserError(_("Các SO gộp phải có cùng SlpCode và U_BusinessUnit theo serial."))
        header_metadata = next((metadata for metadata in serial_item_metadata if metadata), {})
        main._ensure_sap_issue_branch(serial_item_metadata=header_metadata)

        # gom tất cả dòng, không cộng dồn
        lines = []
        for order in self:
            tax_code = order._get_sap_tax_code_for_payload()
            for line in order.order_line:
                line_payload = {
                        "ItemCode": order._get_line_item_code_for_sap(line),
                        "Quantity": line.product_uom_qty,
                        "Price": line.price_unit - line.sap_discount_amount,
                        "WhsCode": order.filler_warehouse_id.code or "",
                        "U_isDiscount": line.sap_is_discount,
                        "U_WarrTime": line.sap_wmonth or 0,
                        "U_OrigiDiscPrcnt": line.discount or 0,
                        "U_OrigiPrice": line.price_unit or 0,
                        "U_DiscAmt": line.sap_discount_amount or 0,
                    }
                if tax_code:
                    line_payload["TaxCode"] = tax_code
                lines.append(line_payload)

        if not lines:
            raise UserError(_("Không có dòng sản phẩm nào để tạo SO trên SAP."))

        warehouse_note = get_sap_request_body_html(main.note or "").strip()
        document_note = get_sap_request_body_html(
            main.document_note
            or (main.ticket_id._build_document_note() if main.ticket_id else "")
        ).strip()

        payload = {
            "CardCode": partners[0].card_code or "",
            "PostingDate": get_sap_request_body_date(fields.Date.context_today(main)),
            "DocDueDate": get_sap_request_body_date(
                main.commitment_date or main.expected_date
            ),
            "TaxDate": get_sap_request_body_date(fields.Date.context_today(main)),
            "Comments": document_note,
            "U_IsIssueInvoice": (
                "N" if any(order.is_exchange_1_1 for order in self)
                else (main.sap_is_issue_invoice or "N")
            ),
            "U_isInstall": get_sap_request_body_bool(main.sap_is_install),
            "U_IsCOCQ": get_sap_request_body_bool(main.sap_is_cocq),
            "U_IsSetup": get_sap_request_body_bool(main.sap_is_setup),
            "Address2": (address2 or "").strip(),
            "U_VoucherTypeID": sap_voucher_type,
            "U_Store": main._compute_store_for_sap(serial_item_metadata=header_metadata),
            "U_NoteForAll": document_note,
            "U_NoteForWhs": warehouse_note,
            "Lines": lines,
        }
        payload.update(header_metadata)
        payload["U_Reasons"] = sap_reason.code or ""
        return payload



    def action_create_sap_so_batch(self):
        """
        Gọi từ list view:
        - Mỗi SO vẫn được 'qua bước' (như create_sap_doc)
        - Gộp SO thành 1 SO SAP
        """
        if not self:
            raise UserError(_("Không có báo giá nào được chọn."))

        # qua bước cho từng SO trước
        # chỉ lấy workflow_1
        orders = self.filtered(lambda o: o.wf_external_id == 'workflow_1')
        if not orders:
            raise UserError(_("Không có báo giá thuộc workflow_1 để tạo SO SAP."))

        payload = orders._prepare_sap_so_batch_payload()

        header = orders._get_sap_headers_safe()
        api_base_url = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("dat_sync_sap.sap_api_url")
        )
        if not api_base_url:
            raise UserError(_("Chưa cấu hình dat_sync_sap.sap_api_url."))

        api_link = "/CreateSOForWarrFix"

        _logger.info(
            "Create batch SO SAP request: url=%s, headers(no-auth)=%s, payload=%s",
            f"{api_base_url}{api_link}",
            {k: v for k, v in header.items() if k.lower() != "authorization"},
            json.dumps(payload, ensure_ascii=False),
        )

        response = requests.post(
            f"{api_base_url}{api_link}", headers=header, json=payload
        )

        _logger.info(
            "Create batch SO SAP response: http_status=%s, text=%s",
            response.status_code,
            response.text,
        )

        if response.status_code != 200:
            debug_json = {
                "request": payload,
                "response_text": response.text,
            }
            raise UserError(
                _("Failed to create batch SO in SAP (HTTP %s): %s")
                % (
                    response.status_code,
                    json.dumps(debug_json, ensure_ascii=False),
                )
            )

        res_json = response.json() or {}
        status = (res_json.get("status") or "").lower()
        msg = res_json.get("msg") or ""
        docnumber = res_json.get("docnumber")

        if status == "true":
            if not docnumber:
                raise UserError(_("SAP trả về thành công nhưng không có số SO. Response: %s") % res_json)
            for index, order in enumerate(orders):
                vals = dict(order._prepare_confirmation_values())
                vals["sap_status"] = docnumber
                if index == 0:
                    vals["name"] = docnumber
                order.write(vals)
            # *** QUAN TRỌNG: không return True ***
            return False   # hoặc chỉ "return"
        else:
            debug_json = {
                "request": payload,
                "response": res_json,
            }

            _logger.error(
                "Create batch SO SAP failed: %s",
                json.dumps(debug_json, ensure_ascii=False),
            )

            raise UserError(
                _(
                    "Failed to create batch SO in SAP: %(status)s | %(msg)s\n\nJSON debug:\n%(json)s"
                )
                % {
                    "status": res_json.get("status"),
                    "msg": msg or "No message",
                    "json": json.dumps(debug_json, ensure_ascii=False, indent=2),
                }
            )



class SapVoucherReason(models.Model):
    _name = "sap.voucher.reason"
    _description = "SAP Voucher Reason"

    name = fields.Char(string="Lý do", required=True)
    code = fields.Char(string="Mã lý do", required=True)
    voucher_type = fields.Char(string="Voucher Type", required=True, index=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "code_voucher_type_uniq",
            "unique(code, voucher_type)",
            "Mã lý do cho mỗi Voucher Type phải là duy nhất.",
        ),
    ]
