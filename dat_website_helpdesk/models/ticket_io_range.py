from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class TicketIORange(models.Model):
    _name = 'ticket.helpdesk.io.range'
    _description = 'Helpdesk IO Quantity Ranges'
    _order = 'min_qty'

    name = fields.Char(
        string='Category Name',
        required=True,
        help='E.g. Small, Medium, Large'
    )
    min_qty = fields.Float(
        string='Min Quantity',
        required=True,
        help='Inclusive lower bound'
    )
    max_qty = fields.Float(
        string='Max Quantity',
        help='Inclusive upper bound; leave zero or blank for “no limit”'
    )

    @api.constrains('min_qty', 'max_qty')
    def _check_no_overlap(self):
        for rec in self:
            # sanity: min <= max (unless max == 0 => no limit)
            if rec.max_qty and rec.min_qty > rec.max_qty:
                raise ValidationError(_('Min Quantity (%s) cannot be greater than Max Quantity (%s).')
                                      % (rec.min_qty, rec.max_qty))

            # compute “infinite” upper bound if max_qty == 0
            rec_upper = float('inf') if rec.max_qty == 0 else rec.max_qty

            # look at all the other ranges
            others = self.search([('id', '!=', rec.id)])
            for other in others:
                other_upper = float('inf') if other.max_qty == 0 else other.max_qty
                # overlap if rec.min ≤ other_upper AND other.min ≤ rec_upper
                if rec.min_qty < other_upper and other.min_qty < rec_upper:
                    raise ValidationError(_(
                        'IO range [%s – %s] overlaps with existing range [%s – %s].'
                    ) % (
                        rec.min_qty,
                        rec.max_qty or _('∞'),
                        other.min_qty,
                        other.max_qty or _('∞'),
                    ))
