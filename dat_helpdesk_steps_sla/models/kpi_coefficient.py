from odoo import api, fields, models


class KpiCoefficient(models.Model):
    _name = 'kpi.coefficient'
    _description = 'KPI Coefficient'

    ticket_id = fields.Many2one('ticket.helpdesk', string='Ticket')
    user_id = fields.Many2one('res.users', string='User', required=True)
    coefficient = fields.Selection([('1', '1'), ('1.5', '1.5'), ('2', '2')])

    _sql_constraints = [('ticket_user_uniq', 'unique (ticket_id,user_id)',
                         'The User cannot be duplicated!')]
