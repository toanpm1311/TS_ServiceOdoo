import json
from email.policy import default

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta


class TicketHelpDesk(models.Model):
    _inherit = 'ticket.helpdesk'

    WORKFLOW_1 = 'dat_website_helpdesk.workflow_1'
    WORKFLOW_2 = 'dat_website_helpdesk.workflow_2'
    WORKFLOW_3 = 'dat_website_helpdesk.workflow_3'
    WORKFLOW_4 = 'dat_website_helpdesk.workflow_4'

    technical_proposal_ids = fields.One2many(
        'technical.proposal',
        'ticket_id',
        string='Technical Proposals',
    )

    @api.depends('step_id', 'status', 'workflow_id')
    def _compute_next_step_button(self):
        for rec in self:
            step_id = rec.step_id.id if rec.step_id else None

            if (step_id == self.env.ref(self.WORKFLOW_3_STEP_6).id and not self.technical_proposal_ids) or\
                    (step_id == self.env.ref(self.WORKFLOW_4_STEP_7).id and self.need_button_approve):
                rec.next_step_button_invisible = True
                rec.next_step_button_name = False
            else:
                super()._compute_next_step_button()

    def action_create_quotation(self):
        if self.step_id.id == self.env.ref(self.WORKFLOW_3_STEP_8).id:
            self.ensure_one()
            tp = self.technical_proposal_ids.filtered('is_final_version')
            if tp and tp.attachment_ids:
                return {
                    'name': _('Quotation'),
                    'view_mode': 'form',
                    'res_model': 'sale.order',
                    'type': 'ir.actions.act_window',
                    'target': 'new',
                    'context': self._prepare_sale_order_action_context({
                        'default_ticket_id': self.id,
                        'default_company_id': self.branch.id,
                        'default_partner_id': self.customer_id.id,
                        'default_order_line': [],
                        'default_proposal_attachment_ids': [(6, 0, tp.attachment_ids.ids)],
                        'default_sc_sale_order_attachment_ids': [],
                        'from_ticket_helpdesk': True,
                        'dialog_size': 'extra-large',
                    }),
                }
            technical_lines = tp.technical_proposal_line_ids if tp else self.technical_proposal_ids.mapped(
                'technical_proposal_line_ids')
            order_lines = [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                })
                for line in technical_lines
            ]
            return {
                'name': _('Quotation'),
                'view_mode': 'form',
                'res_model': 'sale.order',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'context': self._prepare_sale_order_action_context({
                    'default_ticket_id': self.id,
                    'default_company_id': self.branch.id,
                    'default_partner_id': self.customer_id.id,
                    'default_order_line': order_lines,
                    'default_proposal_attachment_ids': [],
                    'default_sc_sale_order_attachment_ids': [],
                    'from_ticket_helpdesk': True,
                    'dialog_size': 'extra-large',
                }),
            }
        else:
            return super(TicketHelpDesk, self).action_create_quotation()

    def action_create_technical_proposal(self):
        return {
            'name': _('Technical Proposal'),
            'view_mode': 'form',
            'res_model': 'technical.proposal',
            'type': 'ir.actions.act_window',
            'context': {
                'default_ticket_id': self.id,
            },
            'target': 'new',
        }

    def _technical_proposal_json_dumps(self, value):
        return json.dumps(value or {}, ensure_ascii=False, indent=2, default=str)

    def _technical_proposal_log_json(self, title, payload):
        self.ensure_one()
        try:
            self.message_post(
                body='<b>%s</b><pre>%s</pre>' % (
                    title,
                    self._technical_proposal_json_dumps(payload),
                )
            )
        except Exception:
            pass

    def action_create_material_proposal_with_json(self):
        self.ensure_one()
        TechnicalProposal = self.env['technical.proposal'].with_context(
            default_ticket_id=self.id
        )
        default_values = TechnicalProposal.default_get([
            'ticket_id',
            'technical_proposal_line_ids',
        ])
        proposal_vals = {
            'name': _('Đề xuất vật tư - %s') % (self.name or self.display_name),
            'ticket_id': self.id,
            'is_final_version': True,
        }
        if default_values.get('technical_proposal_line_ids'):
            proposal_vals['technical_proposal_line_ids'] = default_values['technical_proposal_line_ids']

        request_json = {
            'model': 'technical.proposal',
            'method': 'create',
            'ticket': {
                'id': self.id,
                'name': self.name,
                'customer': self.customer_id.display_name if self.customer_id else '',
                'owner': self.owner_id.display_name if self.owner_id else '',
                'serial': self.stock_lot_id.name if self.stock_lot_id else '',
                'product': self.product_id.display_name if self.product_id else '',
            },
            'values': proposal_vals,
        }

        self.technical_proposal_ids.filtered('is_final_version').write({
            'is_final_version': False,
            'is_locked': True,
        })
        proposal = TechnicalProposal.create(proposal_vals)
        response_json = {
            'id': proposal.id,
            'name': proposal.name,
            'version': proposal.version,
            'is_final_version': proposal.is_final_version,
            'line_count': len(proposal.technical_proposal_line_ids),
            'lines': [
                {
                    'product_id': line.product_id.id,
                    'product_code': line.product_id.default_code or '',
                    'product_name': line.product_id.display_name,
                    'quantity': line.quantity,
                    'description': line.description or '',
                    'note': line.note or '',
                }
                for line in proposal.technical_proposal_line_ids
            ],
        }
        self._technical_proposal_log_json(
            _('Tạo đề xuất vật tư - JSON gửi/nhận'),
            {
                'request': request_json,
                'response': response_json,
            },
        )
        return {
            'name': _('Đề xuất vật tư'),
            'res_model': 'technical.proposal',
            'res_id': proposal.id,
            'view_mode': 'form',
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def action_open_technical_proposal(self):
        technical_proposal_ids = self.technical_proposal_ids
        if len(technical_proposal_ids) == 1:
            return {
                'name': _('Technical Proposal'),
                'res_model': 'technical.proposal',
                'view_id': False,
                'res_id': technical_proposal_ids.id,
                'view_mode': 'form',
                'type': 'ir.actions.act_window',
            }
        else:
            return {
                'name': _('Technical Proposal'),
                'domain': [('ticket_id', '=', self.id)],
                'res_model': 'technical.proposal',
                'view_id': False,
                'view_mode': 'tree,form',
                'type': 'ir.actions.act_window',
            }

    def action_next_step_wf3_step6_provide_tech_solutions(self):
        if not self.technical_proposal_ids:
            raise UserError(_("Please create a technical proposal before moving to the next step."))
        self.technical_proposal_ids.filtered(lambda tp: tp.is_final_version).write({'is_locked': True})
        super(TicketHelpDesk, self).action_next_step_wf3_step6_provide_tech_solutions()

    def action_return_step(self, return_step_reason=False):
        if self.step_id == self.env.ref(self.WORKFLOW_3_STEP_7):
            self.technical_proposal_ids.filtered(lambda tp: tp.is_final_version).write({'create_new_version': True})
            self.technical_proposal_ids.filtered(lambda tp: tp.is_final_version).write({'is_locked': False})
        super().action_return_step()

    def action_next_step_wf3_step8_prepare_quotation(self):
        if not self.sale_order_ids:
            raise ValidationError(_('You must create a sale order and provide feedback before proceeding to the next step.'))
        super(TicketHelpDesk, self).action_next_step_wf3_step8_prepare_quotation()

    def action_next_step_wf3_step9_provide_quotation(self):
        if self.quotation_approval_result in ('resurvey','change_technical_solution'):
            self.technical_proposal_ids.filtered(lambda tp: tp.is_final_version).write({'create_new_version': True})
            self.technical_proposal_ids.filtered(lambda tp: tp.is_final_version).write({'is_locked': False})

        super(TicketHelpDesk, self).action_next_step_wf3_step9_provide_quotation()

    def action_create_deployment_request_processing_ticket(self):
        self.ensure_one()
        ticket_child = super(TicketHelpDesk, self).action_create_deployment_request_processing_ticket()
        final_tp = self.technical_proposal_ids.filtered(lambda tp: tp.is_final_version)
        if final_tp:
            final_tp.copy({'ticket_id': ticket_child.id})
        return ticket_child
