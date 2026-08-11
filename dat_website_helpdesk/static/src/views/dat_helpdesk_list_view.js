/** @odoo-module */

import { listView } from '@web/views/list/list_view';
import { registry } from "@web/core/registry";
import { HelpdeskTicketListController as Controller } from './dat_helpdesk_list_controller.js';

export const HelpdeskTicketListView = {
    ...listView,
    Controller,
    buttonTemplate: 'create_multi_tickets.ListView.Buttons',
};

registry.category("views").add("create_multi_tickets_list", HelpdeskTicketListView);
