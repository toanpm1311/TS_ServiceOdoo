from odoo import _, fields, models, api


class TicketHelpdeskAssignmentFollower(models.Model):
    _name = 'ticket.helpdesk.assignment.follower'
    _description = 'Helpdesk Assignment Follower'

    branch_id = fields.Many2one(
        'res.company',
        string='Branch',
        compute_sudo=True,
        required=True,
        domain=lambda self: [('id', 'in', self.sudo().env.ref('base.main_company').child_ids.ids)])
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        domain="[('company_id', '=', branch_id)]",
        required=True,
    )
    ticket_type_id = fields.Many2one(
        'helpdesk.type',
        string='Ticket Type',
        required=True,
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Employee',
        required=True,
    )

    _sql_constraints = [
        (
            'unique_branch_dept_type',
            'unique(branch_id, department_id, ticket_type_id)',
            'A mapping for this Branch / Department / Ticket Type already exists.'
        ),
    ]

    @api.onchange('branch_id')
    def _onchange_branch(self):
        if self.department_id and self.department_id.company_id != self.branch_id:
            self.department_id = False
