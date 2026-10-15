// Controller behavior without requiring an Odoo server or sending RPCs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/src/views/dat_helpdesk_list_controller.js'), 'utf8');
const controllerSource = source.replace(/^import .*;\r?\n/gm, '').replace('export class', 'class');
const localDate = (value, extraDays = 0) => {
    const time = Date.parse(value + 'T00:00:00+07:00');
    return {
        isValid: Number.isFinite(time),
        time: time + extraDays * 86400000,
        startOf() { return this; },
        plus({ days }) { return localDate(value, extraDays + days); },
    };
};
const Controller = new Function('ListController', 'useState', 'useService', 'deserializeDate', 'serializeDateTime', '_t',
    controllerSource + '\nreturn HelpdeskTicketListController;')(
        class {}, value => value, () => null, localDate,
        date => new Date(date.time).toISOString().slice(0, 19).replace('T', ' '),
        (text, ...args) => args.reduce((result, value) => result.replace('%s', value), text),
    );
const controller = new Controller();
const groups = new Map([[1, { description: 'Existing customer and status', domain: [['owner_id', '=', 7], ['status', '=', 'in_progress']] }]]);
let nextId = 2;
controller.env = { searchModel: {
    createNewFilters(filters) {
        for (const filter of filters) {
            filter.groupId = nextId++;
            groups.set(filter.groupId, filter);
        }
    },
    deactivateGroup(id) { groups.delete(id); },
} };
controller.companyService = {
    activeCompanyIds: [2, 3],
    getCompany: id => ({ id, name: id === 2 ? 'HCM' : 'Ha Noi' }),
};
const warnings = [];
controller.notification = { add: message => warnings.push(message) };
controller.ticketScope = { dateFrom: '2026-10-15', dateTo: '2026-10-15', branchId: '2' };
controller.onApplyTicketScope();
assert.deepEqual(controller.ticketScopeFilter.domain, [
    ['create_date', '>=', '2026-10-14 17:00:00'],
    ['create_date', '<', '2026-10-15 17:00:00'],
    ['branch', '=', 2],
]);
assert.equal(groups.size, 2);
assert.equal(groups.get(1).domain[0][0], 'owner_id');
controller.ticketScope.dateTo = '2026-10-16';
controller.onApplyTicketScope();
assert.equal(groups.size, 2, 'Changing the scope must replace its old filter');
const applied = controller.ticketScopeFilter;
controller.ticketScope.dateFrom = '2026-10-20';
controller.onApplyTicketScope();
assert.equal(controller.ticketScopeFilter, applied, 'Invalid dates must preserve the applied query');
assert.equal(warnings.length, 1);
controller.ticketScope = { dateFrom: '', dateTo: '', branchId: '999' };
controller.onApplyTicketScope();
assert.equal(controller.ticketScopeFilter, applied, 'Inactive company must not be applied');
assert.equal(warnings.length, 2);
controller.onClearTicketScope();
assert.equal(groups.size, 1);
assert(groups.has(1), 'Clear must preserve customer and status filters');
controller.ticketScope = { dateFrom: '', dateTo: '2026-10-31', branchId: '' };
controller.onApplyTicketScope();
assert.deepEqual(controller.ticketScopeFilter.domain, [['create_date', '<', '2026-10-31 17:00:00']]);
controller.ticketScope = { dateFrom: '2026-10-31', dateTo: '', branchId: '' };
controller.onApplyTicketScope();
assert.deepEqual(controller.ticketScopeFilter.domain, [['create_date', '>=', '2026-10-30 17:00:00']]);
console.log('PASS: date boundaries, UTC+7 conversion, AND domain, filter replacement, invalid range/company, isolated clear, open date bounds');
