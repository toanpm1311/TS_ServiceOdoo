from odoo import api, fields, models, _


class ServiceWorkChecklist(models.Model):
    _name = 'service.work.checklist'
    _description = 'Phi\u1ebfu ki\u1ec3m tra c\u00f4ng vi\u1ec7c d\u1ecbch v\u1ee5'
    _order = 'ticket_id, sequence, id'

    name = fields.Char(string='N\u1ed9i dung c\u00f4ng vi\u1ec7c', required=True)
    code = fields.Char(string='M\u00e3 c\u00f4ng vi\u1ec7c', readonly=True, copy=False, default=lambda self: _('M\u1edbi'))
    sequence = fields.Integer(default=10)
    ticket_id = fields.Many2one('ticket.helpdesk', string='Phi\u1ebfu y\u00eau c\u1ea7u', required=True, ondelete='cascade', index=True)
    step_id = fields.Many2one('ticket.step', string='B\u01b0\u1edbc')
    assigned_user_id = fields.Many2one('res.users', string='Ng\u01b0\u1eddi ph\u1ee5 tr\u00e1ch')
    is_done = fields.Boolean(string='Ho\u00e0n th\u00e0nh')
    done_date = fields.Datetime(string='Ng\u00e0y ho\u00e0n th\u00e0nh', readonly=True, copy=False)
    note = fields.Text(string='Ghi ch\u00fa')

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            if not vals.get('code') or vals.get('code') == _('M\u1edbi'):
                vals['code'] = sequence.next_by_code('service.work.checklist') or _('M\u1edbi')
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('is_done'):
            vals.setdefault('done_date', fields.Datetime.now())
        elif 'is_done' in vals and not vals.get('is_done'):
            vals.setdefault('done_date', False)
        return super().write(vals)


class ImplementationWork(models.Model):
    _inherit = 'implementation.work'

    @api.model_create_multi
    def create(self, vals_list):
        works = super().create(vals_list)
        works._sync_service_work_checklists()
        return works

    def write(self, vals):
        result = super().write(vals)
        if {'name', 'note', 'approved', 'start_date', 'end_date'} & set(vals):
            self._sync_service_work_checklists()
        return result

    def _sync_service_work_checklists(self):
        checklist_env = self.env['service.work.checklist'].sudo()
        for work in self.filtered('ticket_id'):
            checklist = checklist_env.search([
                ('ticket_id', '=', work.ticket_id.id),
                ('name', '=', work.name),
            ], limit=1)
            vals = {
                'ticket_id': work.ticket_id.id,
                'sequence': work.sequence,
                'name': work.name or _('C\u00f4ng vi\u1ec7c'),
                'note': work.note,
                'is_done': work.approved == 'complete',
                'done_date': work.end_date if work.approved == 'complete' else False,
            }
            if checklist:
                checklist.write(vals)
            else:
                checklist_env.create(vals)
