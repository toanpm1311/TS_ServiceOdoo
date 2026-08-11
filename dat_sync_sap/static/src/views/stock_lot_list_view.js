/** @odoo-module */

import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { SerialItemListController as Controller } from './stock_lot_list_controller.js';

export const SerialItemListView = {
    ...listView,
    Controller,
    buttonTemplate: 'create_serial_item.ListView.Buttons',
};

registry.category("views").add("create_serial_item_list", SerialItemListView);
