/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import {ListController} from '@web/views/list/list_controller';
import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { deserializeDate, serializeDateTime } from "@web/core/l10n/dates";

export class HelpdeskTicketListController extends ListController {
    static template = "dat_website_helpdesk.TicketListView";

    setup() {
        super.setup();
        this.notification = useService("notification");
        this.companyService = useService("company");
        this.ticketScope = useState({ dateFrom: "", dateTo: "", branchId: "" });
        this.ticketScopeFilter = null;
    }

    get ticketBranches() {
        return this.companyService.activeCompanyIds
            .map((id) => this.companyService.getCompany(id))
            .sort((left, right) => left.name.localeCompare(right.name));
    }

    onApplyTicketScope() {
        const { dateFrom, dateTo, branchId } = this.ticketScope;
        if (dateFrom && dateTo && dateFrom > dateTo) {
            this.notification.add(_t("Ngày bắt đầu không được sau ngày kết thúc."), { type: "warning" });
            return;
        }
        const domain = [];
        const descriptions = [];
        if (dateFrom || dateTo) {
            const start = dateFrom ? deserializeDate(dateFrom) : null;
            const end = dateTo ? deserializeDate(dateTo) : null;
            if ((start && !start.isValid) || (end && !end.isValid)) {
                this.notification.add(_t("Vui lòng chọn ngày hợp lệ."), { type: "warning" });
                return;
            }
            if (start) {
                domain.push(["create_date", ">=", serializeDateTime(start.startOf("day"))]);
            }
            if (end) {
                // Exclusive next-day boundary includes the whole selected end date.
                domain.push(["create_date", "<", serializeDateTime(end.plus({ days: 1 }).startOf("day"))]);
            }
            descriptions.push(_t("Ngày tạo: %s → %s", dateFrom || "…", dateTo || "…"));
        }
        if (branchId) {
            const branch = this.ticketBranches.find((company) => company.id === Number(branchId));
            if (!branch) {
                this.notification.add(_t("Vui lòng chọn chi nhánh đang được phép xem."), { type: "warning" });
                return;
            }
            domain.push(["branch", "=", branch.id]);
            descriptions.push(_t("Chi nhánh: %s", branch.name));
        }
        this.clearTicketScopeFilter();
        if (domain.length) {
            // One composite filter keeps dates AND branch together. Its group is
            // ANDed by SearchModel with existing customer/status/favorite filters.
            const filter = { description: descriptions.join(" · "), domain };
            this.env.searchModel.createNewFilters([filter]);
            this.ticketScopeFilter = filter;
        }
    }

    clearTicketScopeFilter() {
        if (this.ticketScopeFilter) {
            this.env.searchModel.deactivateGroup(this.ticketScopeFilter.groupId);
            this.ticketScopeFilter = null;
        }
    }

    onClearTicketScope() {
        this.clearTicketScopeFilter();
        Object.assign(this.ticketScope, { dateFrom: "", dateTo: "", branchId: "" });
    }

    OnCreateTicketClick() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'create.ticket.wizard',
            name: _t('Create Ticket'),
            view_mode: 'form',
            view_type: 'form',
            views: [[false, 'form']],
            target: 'new',
            res_id: false,
            context: {
                'dialog_size': 'extra-large',
            }
        });
    }
}
