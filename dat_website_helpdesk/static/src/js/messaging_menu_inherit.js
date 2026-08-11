/* @odoo-module */

import { MessagingMenu } from "@mail/core/web/messaging_menu";
import { patch } from "@web/core/utils/patch";

patch(MessagingMenu.prototype, {
    onClickThread(isMarkAsRead, thread) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: thread.model,
            views: [[false, "form"]],
            res_id: thread.id,
        });
        this.markAsRead(thread);
    }
});