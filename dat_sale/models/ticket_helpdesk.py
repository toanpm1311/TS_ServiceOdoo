import logging
import re
from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TicketHelpDesk(models.Model):
    _inherit = 'ticket.helpdesk'

    sale_order_feedback = fields.Selection([('agree', 'Agree'),('refuse', 'Refuse')],string='Sale Order Feedback', default=False, compute='_compute_sale_order_feedback', store=True)
    sale_order_feedback_comment = fields.Text(string='Sale Order Feedback Comment', compute='_compute_sale_order_feedback', default=False, store=True)

    @api.depends('sale_order_ids.status')
    def _compute_sale_order_feedback(self):
        for rec in self:
            if rec.sale_order_ids:
                if rec.sale_order_ids[0].status == 'confirmed':
                    rec.sale_order_feedback = 'agree'
                    rec.sale_order_feedback_comment = False
                elif rec.sale_order_ids[0].status in ('rejected','cancelled'):
                    rec.sale_order_feedback = 'refuse'
                    rec.sale_order_feedback_comment = rec.sale_order_ids[0].reject_reason or rec.sale_order_ids[0].cancel_reason
                else:
                    rec.sale_order_feedback = False
                    rec.sale_order_feedback_comment = False
