/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { ListController } from "@web/views/list/list_controller";

export class SerialItemListController extends ListController {
    setup() {
        super.setup();
        console.log("SerialItemListController loaded");
    }

    onCreateSerialItemClick() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'create.serial.wizard',
            name: _t('Đồng bộ SerialNumber'),
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'new',
            context: {
                dialog_size: 'extra-large',
            }
        });
    }

}
