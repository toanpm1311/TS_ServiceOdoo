from odoo import _, api, fields, models


class TicketRating(models.Model):
    _name = 'ticket.rating'
    _description = 'Ticket Rating'

    note = fields.Text(string='Note')
    rate = fields.Integer()
    submit_dt = fields.Date(
        string='Submit Date',
        default=fields.Datetime.now,
    )
    zalo_msg_ref = fields.Char(
        string='Message ID',
        help='The ID of the message in the Zalo ZNS, used for tracking and reference.',
    )
    zalo_msg_id = fields.Many2one(
        'zalo.zns.message',
        string='Zalo Message',
        compute='_compute_zalo_msg_id',
        precompute=True,
        store=True,
        ondelete='cascade',
        help='The Zalo ZNS message associated with this rating.',
    )
    feedbacks = fields.Json()
    zalo_tracking_id = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_ticket_rating()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'rate', 'note', 'zalo_msg_ref', 'zalo_msg_id'} & set(vals):
            self._sync_ticket_rating()
        return result

    _sql_constraints = [
        ("zalo_msg_ref_unique", "unique(zalo_msg_ref)",
         _("The zalo_msg_ref must be unique.")),
    ]

    @api.depends('zalo_msg_ref')
    def _compute_zalo_msg_id(self):
        for record in self:
            zalo_msg = self.env['zalo.zns.message'].search(
                [('zalo_msg_id', '=', record.zalo_msg_ref)], limit=1)
            record.zalo_msg_id = zalo_msg.id
            if not zalo_msg:
                continue
            ticket = self.env['ticket.helpdesk'].browse(
                zalo_msg.record_id).exists()
            if not ticket:
                continue
            record._sync_ticket_rating(ticket)

    def _get_ticket(self):
        self.ensure_one()
        if not self.zalo_msg_id:
            return self.env['ticket.helpdesk']
        if self.zalo_msg_id.helpdesk_ticket_id:
            return self.zalo_msg_id.helpdesk_ticket_id.exists()
        if self.zalo_msg_id.model_id.model == 'ticket.helpdesk' and self.zalo_msg_id.record_id:
            return self.env['ticket.helpdesk'].browse(self.zalo_msg_id.record_id).exists()
        return self.env['ticket.helpdesk']

    def _sync_ticket_rating(self, ticket=False):
        for record in self:
            rating_ticket = ticket or record._get_ticket()
            if not rating_ticket:
                continue
            vals = {'ticket_rating': record.id}
            if record.rate:
                vals['customer_rating'] = str(record.rate)
            if record.note:
                vals['review'] = record.note
            rating_ticket.with_context(skip_ticket_rating_sync=True).sudo().write(vals)
