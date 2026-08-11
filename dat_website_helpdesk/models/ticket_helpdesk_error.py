from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HelpdeskTicketError(models.Model):
    _name = 'ticket.helpdesk.error'
    _inherit = 'abstract.uuid'
    _description = 'Helpdesk Ticket Error'

    ticket_id = fields.Many2one(
        comodel_name='ticket.helpdesk',
        string='Helpdesk Ticket',
        ondelete='cascade',
        required=True,
        index=True,
    )
    activity = fields.Many2one(
        'implementation.work.template',
        string='Implementation Work',
    )
    date_detected = fields.Date(
        string='Date Detected',
        required=True,
        default=fields.Datetime.now,
    )
    detected_by = fields.Many2one(
        comodel_name='res.users',
        string='Detected By',
        required=True,
        default=lambda self: self.env.user.id,
    )
    description = fields.Text(
        string='Error Description',
        required=True,
    )
    severity = fields.Selection(
        selection=[
            ('high', 'High'),
            ('medium', 'Medium'),
            ('low', 'Low'),
        ],
        string='Severity',
        default='low',
        required=True,
    )
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='ticket_error_attachment_rel',
        column1='error_id',
        column2='attachment_id',
        string='Attachments',
    )
    state = fields.Selection(
        selection=[
            ('new', 'New'),
            ('in_progress', 'In Progress'),
            ('done', 'Resolved'),
            ('cannot_fix', 'Cannot Fix'),
            ('waiting_spare', 'Waiting for Parts'),
        ],
        string='Status',
        default='new',
        required=True,
    )
    resolution = fields.Text(
        string='Resolution Notes',
        required=True,
    )
    date_resolved = fields.Date(
        string='Date Resolved',
        compute='_compute_date_resolved',
        store=True,
        readonly=False,
    )
    acceptance_status = fields.Selection([
        ('before_acceptance', 'Before Acceptance'),
        ('after_acceptance', 'After Acceptance'),
    ],
        string='Acceptance Status',
        copy=False,
    )

    @api.model
    def create(self, vals):
        if 'acceptance_status' in vals and not vals['acceptance_status']:
            ticket = self.env['ticket.helpdesk'].browse(vals.get('ticket_id'))
            acceptance_step = self.env.ref('dat_website_helpdesk.step_wf4_acceptance_completion')
            vals['acceptance_status'] = (
                'after_acceptance'
                if ticket.step_id == acceptance_step and ticket.status != 'in_progress'
                else 'before_acceptance'
            )
        return super(HelpdeskTicketError, self).create(vals)

    @api.depends('state')
    def _compute_date_resolved(self):
        for record in self:
            if record.state == 'done' and not record.date_resolved:
                record.date_resolved = fields.Datetime.now()
            elif record.state != 'done':
                record.date_resolved = False

    @api.constrains('ticket_id', 'date_detected', 'date_resolved')
    def _check_no_overlap_intervals(self):
        for rec in self:
            if not (rec.date_detected and rec.date_resolved):
                continue
            overlapping_count = self.search_count([
                ('id', '!=', rec.id),
                ('ticket_id', '=', rec.ticket_id.id),
                ('date_resolved', '!=', False),
                ('date_detected', '<=', rec.date_resolved),
                ('date_resolved', '>=', rec.date_detected),
            ])
            if overlapping_count:
                raise ValidationError(_(
                    "Khoảng thời gian [%s → %s] đang trùng với một khoảng thời gian khác trong nhật kí hiện trường."
                ) % (rec.date_detected, rec.date_resolved))
            
    def action_delete_error(self):
        """
        Open wizard to confirm deletion of selected error records.
        """
        self.ensure_one()
        wizard = self.env['ticket.error.delete.wizard'].create({
            'error_id': self.id,
        })
        return {
            'name': _('Xác nhận xóa nhật ký hiện trường'),
            'type': 'ir.actions.act_window',
            'res_model': 'ticket.error.delete.wizard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': wizard.id,
            'context': self.env.context,
        }
