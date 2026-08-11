/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import {ListController} from '@web/views/list/list_controller';

export class HelpdeskTicketListController extends ListController {

    setup() {
        super.setup();
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
