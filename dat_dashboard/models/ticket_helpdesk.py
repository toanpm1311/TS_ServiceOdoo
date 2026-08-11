# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class TicketHelpdesk(models.Model):
    _inherit = 'ticket.helpdesk'

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        related='product_id.product_tmpl_id',
        store=True,
        index=True
    )
    sap_business_unit = fields.Char(
        string='Business Unit',
        related='product_tmpl_id.sap_business_unit',
        store=True,
    )
    product_code = fields.Char(
        string='Item Code',
        related='product_tmpl_id.default_code',
        store=True,
    )
    is_warranty_remote = fields.Selection(
        [('Yes', 'Yes'), ('No', 'No')],
        string='Is Warranty Remote',
        compute='_compute_is_warranty_remote',
        store=True,
    )

    total_time_spent = fields.Float(
        string='Time to Finish',
        compute='_compute_total_time_spent',
        store=True,
    )

    @api.depends('service_action')
    def _compute_is_warranty_remote(self):
        remote_actions = {
            'warranty_at_dat',
            'repair_at_dat',
            'warranty_at_dat_paid',
        }
        for rec in self:
            rec.is_warranty_remote = 'No' if rec.service_action in remote_actions else 'Yes'

    @api.depends('ticket_step_status_ids')
    def _compute_total_time_spent(self):
        for ticket in self:
            ticket.total_time_spent = sum(
                ticket.ticket_step_status_ids.mapped('time_spent') or [0.0]
            )
