import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TicketHelpdesk(models.Model):
    _inherit = "ticket.helpdesk"

    ts_return_so_required = fields.Boolean(string="Cần SO trả hàng", copy=False, readonly=True)
    ts_return_so_requested_at = fields.Datetime(string="Thời điểm yêu cầu SO trả hàng", copy=False, readonly=True)
    ts_return_so_ready = fields.Boolean(
        string="Đã có SO trả hàng",
        compute="_compute_ts_return_so_ready",
        store=True,
    )
    ts_defective_return_status = fields.Selection(
        [
            ("not_sent", "Chưa gửi sản phẩm lỗi"),
            ("sent", "Khách đã gửi sản phẩm lỗi"),
            ("received", "DAT đã nhận sản phẩm lỗi"),
        ],
        string="Trạng thái gửi sản phẩm lỗi",
        copy=False,
        tracking=True,
    )

    @api.depends("sale_order_ids.ts_pair_role")
    def _compute_ts_return_so_ready(self):
        for rec in self:
            rec.ts_return_so_ready = bool(rec.sale_order_ids.filtered(lambda so: getattr(so, "ts_pair_role", False) == "return"))

    def _ts_align_post_message(self, body):
        self.ensure_one()
        if hasattr(self, "_message_log_batch"):
            self._message_log_batch(bodies={self.id: body})
        else:
            self.message_post(body=body)

    def _ts_align_close_ticket(self):
        self.ensure_one()
        step_9_id = self._safe_ref_id(getattr(self, "WORKFLOW_1_STEP_9", ""))
        if step_9_id:
            self.step_id = step_9_id
        else:
            self.status = "closed"
            if hasattr(self, "end_date") and not self.end_date:
                self.end_date = fields.Datetime.now()
        return True

    def _ts_align_set_step_7(self):
        self.ensure_one()
        step_7_id = self._safe_ref_id(getattr(self, "WORKFLOW_1_STEP_7", ""))
        if step_7_id:
            self.step_id = step_7_id
        return True

    def _ts_align_require_received_defective(self):
        self.ensure_one()
        remote = self._wf1_is_remote()
        if remote:
            return False
        return bool(self.is_exchange_1_1 or self.is_return_defective)

    def _ts_align_ensure_remote_defective_return_status(self):
        self.ensure_one()
        if not self._wf1_is_remote():
            return False

        vals = {}
        if self.is_received_defective:
            if self.ts_defective_return_status != "received":
                vals["ts_defective_return_status"] = "received"
        elif not self.ts_defective_return_status:
            vals["ts_defective_return_status"] = "not_sent"

        if vals:
            self.write(vals)
        return True

    @api.onchange("service_action")
    def _onchange_ts_remote_defective_return_status(self):
        for rec in self:
            if rec._wf1_is_remote() and not rec.ts_defective_return_status:
                rec.ts_defective_return_status = "not_sent"

    @api.onchange("is_received_defective")
    def _onchange_ts_defective_return_status_from_received(self):
        for rec in self:
            if rec.is_received_defective:
                rec.ts_defective_return_status = "received"

    @api.onchange("ts_defective_return_status")
    def _onchange_ts_defective_return_status(self):
        for rec in self:
            if rec.ts_defective_return_status == "received":
                rec.is_received_defective = True
                if not rec.received_defective_date:
                    rec.received_defective_date = fields.Datetime.now()
            elif rec.ts_defective_return_status in ("not_sent", "sent"):
                rec.is_received_defective = False

    def _ts_align_requires_customer_delivery_so(self):
        self.ensure_one()
        return bool(
            self.wf_external_id == "workflow_1"
            and self.product_warranty_status == "warranty"
            and self.service_action != "onsite_technical_support"
            and self.require_materials != "yes"
            and not self.is_exchange_1_1
            and not self.is_return_defective
        )

    def _ts_align_set_customer_delivery_so_required(self):
        self.ensure_one()
        if not self._ts_align_requires_customer_delivery_so():
            return False
        self.is_need_new_so = True
        if self._wf1_is_remote():
            self._ts_align_ensure_remote_defective_return_status()
        self._ts_align_post_message(
            _("Phiếu bảo hành/sửa chữa không xuất vật tư vẫn phải tạo SO xuất trả khách trước khi giao trả.")
        )
        return True

    def _ts_align_get_customer_delivery_order(self):
        self.ensure_one()
        return self.sale_order_ids.filtered(lambda so: not getattr(so, "sap_status", False))[:1] or self.sale_order_ids[:1]

    def _ts_align_create_customer_delivery_so_in_sap(self):
        self.ensure_one()
        sale_order = self._ts_align_get_customer_delivery_order()
        if not sale_order:
            raise ValidationError(_("Phiếu này chưa có SO xuất trả khách. Vui lòng tạo SO trước khi giao trả / kết thúc."))

        if getattr(sale_order, "sap_status", False):
            self.sap_sale_order_number = sale_order.sap_status
            return sale_order.sap_status

        so_number = sale_order.create_sap_doc(doc_type="SO")
        if so_number:
            self.sap_sale_order_number = so_number
            message = _("Đã tạo SO xuất trả khách thành công trên SAP với SO number = %s") % so_number
            self._ts_align_post_message(message)
            if "popup_notification" in self._fields:
                self.popup_notification = message
        return so_number

    def _ts_align_create_exchange_so_in_sap(self):
        self.ensure_one()
        sale_order = self._ts_align_get_customer_delivery_order()
        if not sale_order:
            raise ValidationError(_("Đổi 1-1: chưa có SO cho ĐV. Vui lòng tạo SO trước khi giao trả / kết thúc."))

        if getattr(sale_order, "sap_status", False):
            self.sap_sale_order_number = sale_order.sap_status
            return sale_order.sap_status

        so_number = sale_order.create_sap_doc(doc_type="SO")
        if so_number:
            self.sap_sale_order_number = so_number
            message = _("Đã tạo SO đổi 1-1 thành công trên SAP với SO number = %s") % so_number
            self._ts_align_post_message(message)
            if "popup_notification" in self._fields:
                self.popup_notification = message
        return so_number

    def _ts_align_prepare_exchange_so_and_serial(self):
        self.ensure_one()
        has_new_serial = bool(getattr(self, "new_stock_lot_id", False)) or bool(getattr(self, "replace_serial_number", False))
        self.is_need_new_so = True
        self._ensure_exchange_service_so()
        if has_new_serial:
            self._ensure_replace_serial_saved()
        return True

    def _ts_align_mark_return_so_required(self, reason):
        self.ensure_one()
        vals = {
            "ts_return_so_required": True,
            "ts_return_so_requested_at": fields.Datetime.now(),
            "is_need_new_so": True,
        }
        self.write(vals)
        return_body = _(
            "Phiếu bị từ chối nên không tạo ĐXVT. Hệ thống chuyển sang nhánh trả khách và yêu cầu tạo SO trả hàng trước khi giao trả."
        )
        self._ts_align_post_message(return_body)
        if hasattr(self, "_ts_notify_internal_event"):
            self._ts_notify_internal_event(_("Yêu cầu tạo SO trả hàng"), return_body)
        if hasattr(self, "_ts_create_audit_log"):
            self._ts_create_audit_log(
                name=_("Yêu cầu tạo SO trả hàng"),
                change_scope="workflow",
                change_type="guard",
                field_name="ts_return_so_required",
                old_value=False,
                new_value=True,
                reason=reason or return_body,
            )
        return True

    def _ts_align_has_required_return_so(self):
        self.ensure_one()
        return bool(self.sale_order_ids.filtered(lambda so: getattr(so, "ts_pair_role", False) == "return"))

    @api.depends(
        "product_warranty_status",
        "ts_return_so_required",
        "ts_return_so_ready",
        "is_exchange_1_1",
        "is_return_defective",
        "require_materials",
        "step_external_id",
        "service_action",
        "wf_external_id",
    )
    def _compute_create_quotation_button_name(self):
        super()._compute_create_quotation_button_name()
        for rec in self:
            if (
                rec.ts_return_so_required
                and not rec.ts_return_so_ready
            ) or (
                rec.is_exchange_1_1
                and rec.step_external_id in ("step_wf1_confirm_replace_and_serial", "step_wf1_product_delivery")
            ) or (
                rec._ts_align_requires_customer_delivery_so()
                and rec.step_external_id in (
                    "step_wf1_confirm_replace_and_serial",
                    "step_wf1_product_delivery",
                    "step_wf1_technical_done_close",
                )
            ):
                rec.create_quotation_button_name = "create_quotation"

    def action_create_quotation(self):
        action = super().action_create_quotation()
        self.ensure_one()
        if self.is_exchange_1_1:
            ctx = dict(action.get("context") or {})
            ctx.update({
                "default_sap_is_create_so": True,
                "default_sap_is_issue_invoice": "N",
                "default_sap_tax_code": "SVN3",
            })
            action["context"] = ctx

        if self._ts_align_requires_customer_delivery_so():
            ctx = dict(action.get("context") or {})
            product_ids = []
            if self.stock_lot_id and self.stock_lot_id.product_id:
                product_ids = self.stock_lot_id.product_id.ids
            note = _("SO xuất trả khách cho phiếu %s sau bảo hành/sửa chữa không xuất vật tư.") % (self.name or "")
            existing_note = (ctx.get("default_document_note") or "").strip()
            ctx.update({
                "default_product_ids": product_ids,
                "default_origin": self.name,
                "default_client_order_ref": _("%s - SO xuất trả khách") % (self.name or ""),
                "default_document_note": ("%s - %s" % (existing_note, note)).strip(" -"),
                "default_sap_is_create_so": True,
            })
            action["context"] = ctx

        if not self.ts_return_so_required or self.ts_return_so_ready:
            return action

        ctx = dict(action.get("context") or {})
        note = _("SO trả hàng cho phiếu %s do khách từ chối báo giá / đề xuất vật tư.") % (self.name or "")
        existing_note = (ctx.get("default_document_note") or "").strip()
        ctx.update({
            "default_ts_pair_role": "return",
            "default_origin": self.name,
            "default_client_order_ref": _("%s - SO trả hàng") % (self.name or ""),
            "default_document_note": ("%s - %s" % (existing_note, note)).strip(" -"),
        })
        action["context"] = ctx
        return action

    def action_next_step_wf1_step4_material_dispatch(self):
        self.ensure_one()
        if self.sale_order_feedback == "refuse" or getattr(self, "ts_material_proposal_status", False) == "rejected":
            prev_step = self.step_id.name or ""
            if "reassembly" in self._fields:
                self.reassembly = True
            return_step = self.env.ref(self.WORKFLOW_1_STEP_6, raise_if_not_found=False) if hasattr(self, "WORKFLOW_1_STEP_6") else False
            if return_step:
                self.step_id = return_step
            self._ts_align_mark_return_so_required(
                _("ĐXVT bị chặn vì báo giá / đề xuất vật tư bị từ chối. Prev step: %s") % prev_step
            )
            return True

        return super().action_next_step_wf1_step4_material_dispatch()

    def action_next_step_wf1_step2_receiving(self):
        self.ensure_one()

        if self._wf1_is_remote():
            self._ts_align_ensure_remote_defective_return_status()

        result = super().action_next_step_wf1_step2_receiving()

        if self.product_warranty_status != "warranty":
            return result

        if self.service_action == "onsite_technical_support":
            return result

        if self.require_materials == "yes":
            return result

        self._ts_align_set_customer_delivery_so_required()
        self._ts_align_set_step_7()

        route = "bảo hành từ xa" if self._wf1_is_remote() else "bảo hành tại DAT"
        self._ts_align_post_message(
            _("Phiếu còn bảo hành, không cần vật tư. Hệ thống chuyển sang nhánh quyết định 1-1 theo route %s.") % route
        )
        return result

    def action_next_step_wf1_step5a_confirm_replace_and_serial(self):
        self.ensure_one()

        remote = self._wf1_is_remote()
        has_flag = bool(self.is_exchange_1_1 or self.is_return_defective)

        if not has_flag:
            if self._ts_align_requires_customer_delivery_so():
                self._ts_align_set_customer_delivery_so_required()
                return self._ts_align_set_step_7()

            self._ts_align_post_message(
                _("Nhánh %s không phát sinh 1-1 / trả hàng lỗi. Phiếu được kết thúc theo đúng quy trình.")
                % ("bảo hành từ xa" if remote else "bảo hành tại DAT")
            )
            return self._ts_align_close_ticket()

        if self.is_return_defective:
            if remote:
                self._ts_align_ensure_remote_defective_return_status()
            if self._ts_align_require_received_defective() and not self.is_received_defective:
                raise ValidationError(_("Trả hàng lỗi: phải xác nhận 'Đã nhận hàng lỗi?' trước khi xử lý tiếp."))
            if self.is_received_defective and hasattr(self, "received_defective_date") and not self.received_defective_date:
                self.received_defective_date = fields.Datetime.now()
            self._ts_align_post_message(
                _("Phiếu vào nhánh trả hàng lỗi%s.") % (" từ xa, chưa bắt buộc nhận hàng lỗi ở bước này" if remote else "")
            )
            return self._ts_align_set_step_7()

        if self.is_exchange_1_1:
            if remote:
                self._ts_align_ensure_remote_defective_return_status()
            self._ts_align_prepare_exchange_so_and_serial()
            if self._ts_align_require_received_defective() and not self.is_received_defective:
                raise ValidationError(_("Đổi 1-1: phải xác nhận 'Đã nhận hàng lỗi?' trước khi xử lý tiếp."))
            if self.is_received_defective and hasattr(self, "received_defective_date") and not self.received_defective_date:
                self.received_defective_date = fields.Datetime.now()

            self._ts_align_post_message(
                _("Phiếu vào nhánh đổi 1-1%s. Hệ thống đã kiểm tra SO cho ĐV; serial thay thế có thể cập nhật sau.")
                % (" từ xa" if remote else "")
            )
            return self._ts_align_set_step_7()

        return True

    def action_next_step_wf1_step7_product_delivery(self):
        self.ensure_one()

        remote = self._wf1_is_remote()
        need_received_defective = self._ts_align_require_received_defective()
        if remote:
            self._ts_align_ensure_remote_defective_return_status()

        if self.ts_return_so_required and not self._ts_align_has_required_return_so():
            raise ValidationError(_("Phiếu bị từ chối báo giá / vật tư nên phải tạo SO trả hàng trước khi giao trả / kết thúc."))

        if (self.is_exchange_1_1 or self.is_return_defective) and need_received_defective and not self.is_received_defective:
            raise ValidationError(_("Vui lòng xác nhận 'Đã nhận hàng lỗi?' trước khi kết thúc."))

        if self.is_received_defective and hasattr(self, "received_defective_date") and not self.received_defective_date:
            self.received_defective_date = fields.Datetime.now()

        if self.is_exchange_1_1:
            self._ts_align_prepare_exchange_so_and_serial()
            self._ts_align_create_exchange_so_in_sap()

        if self._ts_align_requires_customer_delivery_so():
            self._ts_align_create_customer_delivery_so_in_sap()

        if remote and (self.is_exchange_1_1 or self.is_return_defective) and not self.is_received_defective:
            self._ts_align_post_message(
                _("Phiếu remote %s được phép kết thúc dù chưa xác nhận nhận hàng lỗi ở bước giao trả.")
                % ("đổi 1-1" if self.is_exchange_1_1 else "trả hàng lỗi")
            )
            _logger.info(
                "[TS_ALIGN][WF1][STEP7] ticket=%s remote flow closed without defective receipt confirmation",
                self.name,
            )

        return self._ts_align_close_ticket()
