from odoo import _, models, fields, api
from odoo.exceptions import ValidationError

class TechnicalProposal(models.Model):
    _name = 'technical.proposal'
    _description = 'Technical Proposal'
    _order = 'ticket_id, version desc'

    name = fields.Char(string='Technical Proposal Name', required=True)
    customer_name = fields.Char('Customer', related='ticket_id.customer_id.name', store=True)
    customer_address = fields.Char('Customer Address', related='ticket_id.customer_address', store=True)
    customer_contact_name = fields.Char('Customer Contact Name', related='ticket_id.customer_contact_name', store=True)
    description = fields.Char(string='Technical Proposal Description')
    bom_template = fields.Many2one('technical.proposal.template', string='BOM Template')
    ticket_id = fields.Many2one('ticket.helpdesk', string='Ticket', required=True, index=True)
    version = fields.Integer(string='Technical Proposal Version', readonly=True, default=1)
    technical_proposal_line_ids = fields.One2many('technical.proposal.line', 'technical_proposal_id',
                                                  string='Proposal Lines', copy=True)
    tp_create_date = fields.Datetime(string='Create Date',
        default=lambda self: fields.Datetime.now(), readonly=True)
    tp_create_by = fields.Many2one('res.users', string='Created By',
        default=lambda self: self.env.user, readonly=True)
    bom_type = fields.Selection([('automation', 'Automation'),('energy', 'Energy')], string='BOM Type', compute='_compute_bom_type', store=True)
    create_new_version = fields.Boolean(string='Create New Version', default=False)
    is_locked = fields.Boolean(string='Is Locked', default=False, copy=False)
    is_final_version = fields.Boolean(string='Is Final Version', default=True)
    main_equipment_configuration = fields.Text(string='Main Equipment Configuration')
    technical_solution_description = fields.Text(string='Technical Solution Description')
    images = fields.Binary(string='Images', attachment=True)

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'technical_proposal_attachment_rel',
        'proposal_id',
        'attachment_id',
        string='B.O.M Attachments',
        domain=lambda self: [('res_model', '=', 'technical.proposal')],
    )

    @api.onchange('bom_template')
    def _onchange_bom_template(self):
        existing_products = self.technical_proposal_line_ids.mapped('product_id.id')
        commands = []
        for line in self.technical_proposal_line_ids:
            commands.append((4, line.id))
        for tmpl in self.bom_template.technical_proposal_template_line_ids:
            pid = tmpl.product_id.id
            if pid not in existing_products:
                commands.append((0, 0, {
                    'product_id': pid,
                    'description': tmpl.description,
                    'quantity': tmpl.quantity,
                    'note': tmpl.note,
                }))
        self.technical_proposal_line_ids = commands

    @api.depends('ticket_id.department_id')
    def _compute_bom_type(self):
        for rec in self:
            energy_department = [
                self.env.ref('dat_website_helpdesk.dep_energy_mb').id,
                self.env.ref('dat_website_helpdesk.dep_energy_mt').id,
                self.env.ref('dat_website_helpdesk.dep_energy_mn').id
            ]
            automation_department = [
                self.env.ref('dat_website_helpdesk.dep_automation_mb').id,
                self.env.ref('dat_website_helpdesk.dep_automation_mt').id,
                self.env.ref('dat_website_helpdesk.dep_automation_mn').id
            ]
            if rec.ticket_id.department_id.id in energy_department:
                rec.bom_type = 'energy'
            elif rec.ticket_id.department_id.id in automation_department:
                rec.bom_type = 'automation'
            else:
                rec.bom_type = False

    def get_next_version(self):
        domain = [('ticket_id', '=', self.ticket_id.id)]
        if self.id:
            domain.append(('id', '!=', self.id))
        latest_version = self.env['technical.proposal'].search(
            domain, order='version desc', limit=1
        ).version or 0
        version = latest_version + 1
        return version

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form':
            for field in arch.xpath("//sheet//field[not(ancestor::field)]"):
                readonly_condition = field.attrib.get('readonly', "is_locked")
                field.set('readonly', f"{readonly_condition} or is_locked")
        return arch, view

    @api.model
    def create(self, vals):
        if 'version' not in vals:
            vals['version'] = self.get_next_version()
        res = super(TechnicalProposal, self).create(vals)
        return res

    def write(self, vals):
        # Ensure version is recomputed on write
        for rec in self:
            if rec.create_new_version and list(vals.keys() - {'create_new_version', 'is_final_version', 'is_locked'}):
                rec.copy({'is_locked': True, 'version': rec.version, 'is_final_version': False})
                vals['tp_create_date'] = fields.Datetime.now()
                vals['tp_create_by'] = self.env.user.id
                vals['version'] = rec.version + 1
                vals['create_new_version'] = False

        result = super(TechnicalProposal, self).write(vals)
        return result
