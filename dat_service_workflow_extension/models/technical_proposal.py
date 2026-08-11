from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class TechnicalProposal(models.Model):
    _inherit = 'technical.proposal'

    main_product_id = fields.Many2one(
        'product.product',
        string='S\u1ea3n ph\u1ea9m ch\u00ednh',
        related='ticket_id.product_id',
        readonly=True,
    )
    main_product_code = fields.Char(
        string='M\u00e3 s\u1ea3n ph\u1ea9m ch\u00ednh',
        related='main_product_id.default_code',
        readonly=True,
    )
    manufacturer_warranty_month = fields.Integer(
        string='B\u1ea3o h\u00e0nh h\u00e3ng (th\u00e1ng)',
        related='main_product_id.sap_wmonth_dist',
        readonly=True,
    )
    manufacturer_warranty_end_date = fields.Datetime(
        string='Ng\u00e0y h\u1ebft h\u1ea1n b\u1ea3o h\u00e0nh h\u00e3ng',
        related='ticket_id.manufacturer_warranty_end_date',
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        ticket_id = values.get('ticket_id') or self.env.context.get('default_ticket_id')
        if not ticket_id or values.get('technical_proposal_line_ids'):
            return values

        ticket = self.env['ticket.helpdesk'].browse(ticket_id)
        product = ticket._get_main_quotation_product() if ticket.exists() else False
        if product:
            values['technical_proposal_line_ids'] = [(0, 0, {
                'product_id': product.id,
                'description': product.display_name,
                'quantity': 1.0,
                'default_main_code': product.default_code or '',
            })]
        return values


class TechnicalProposalLine(models.Model):
    _inherit = 'technical.proposal.line'

    default_main_code = fields.Char(string='M\u00e3 s\u1ea3n ph\u1ea9m ch\u00ednh')
    manufacturer_warranty_month = fields.Integer(
        string='B\u1ea3o h\u00e0nh h\u00e3ng (th\u00e1ng)',
        related='product_id.sap_wmonth_dist',
        readonly=True,
    )
    manufacturer_warranty_end_date = fields.Datetime(
        string='Ng\u00e0y h\u1ebft h\u1ea1n b\u1ea3o h\u00e0nh h\u00e3ng',
        compute='_compute_manufacturer_warranty_end_date',
    )

    @api.depends('product_id', 'technical_proposal_id.ticket_id.stock_lot_id.warranty_start_date')
    def _compute_manufacturer_warranty_end_date(self):
        for line in self:
            start_date = line.technical_proposal_id.ticket_id.stock_lot_id.warranty_start_date
            months = line.product_id.sap_wmonth_dist
            line.manufacturer_warranty_end_date = start_date + relativedelta(months=months) if start_date and months else False

    @api.onchange('product_id')
    def _onchange_product_id_service_extension(self):
        for line in self:
            if line.product_id:
                line.default_main_code = line.product_id.default_code or ''
                line.onhand_quantity = line.product_id.qty_available
