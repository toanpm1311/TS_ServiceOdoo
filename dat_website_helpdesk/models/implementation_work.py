from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ImplementationWork(models.Model):
    _name = 'implementation.work'
    _inherit = 'abstract.uuid'
    _description = 'Task Allocation'

    ticket_id = fields.Many2one('ticket.helpdesk', string='Ticket')
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Name')
    approved = fields.Selection([('inprogress', 'Inprogress'), ('complete', 'Complete'), ('cancel', 'Cancel')], string='Status')
    is_for_automation_dep = fields.Boolean(
        string='For Automation Department',
        default=False,
        help='Check if this task template is intended for team Auto.'
    )
    is_for_energy_dep = fields.Boolean(
        string='For Energy Department',
        default=False,
        help='Check if this task template is intended for team Energy.'
    )
    start_date = fields.Datetime(
        string='Start Date',
        compute='_compute_date',
        store=True,
        readonly=False,
    )
    end_date = fields.Datetime(
        string='End Date',
        compute='_compute_date',
        store=True,
        readonly=False,
    )
    note = fields.Text(string='Note')

    @api.depends('approved')
    def _compute_date(self):
        for record in self:
            if record.approved:
                if not record.start_date:
                    record.start_date = fields.Datetime.now()
                if not record.end_date:
                    record.end_date = fields.Datetime.now()

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(
                    _("Hạng mục công việc '%s' ngày bắt đầu phải nhỏ hơn ngày kết thúc.") % (
                        record.name
                    )
                )

class ImplementationWorkTemplate(models.Model):
    _name = 'implementation.work.template'
    _inherit = 'abstract.uuid'
    _description = 'Task Allocation Template'

    name = fields.Char(string='Name', required=True)
    is_for_automation_dep = fields.Boolean(
        string='For Automation Department',
        default=False,
        help='Check if this task template is intended for team Auto.'
    )
    is_for_energy_dep = fields.Boolean(
        string='For Energy Department',
        default=False,
        help='Check if this task template is intended for team Energy.'
    )
    active = fields.Boolean(string='Active', default=True)
