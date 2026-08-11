from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class HelpdeskWorkflow(models.Model):
    _inherit = 'helpdesk.workflow'

    percent_warning = fields.Float('Warning when exceeded', default=0.7, required=True)
    template_zalo_review = fields.Many2one('zalo.zns.template', string='Zalo Template Review',
                                    ondelete='cascade')

    @api.constrains('percent_warning')
    def _check_percent_warning(self):
        for record in self:
            if record.percent_warning < 0 or record.percent_warning > 1:
                raise ValidationError(_("The percentage value must be between 0 and 100."))

    @api.constrains('step_ids')
    def _check_notify_zalo_template(self):
        for workflow in self:
            for step in workflow.step_ids:
                if step.notify_zalo and not step.template_zalo:
                    raise ValidationError(
                        _('Zalo template must be set for step "%s" in workflow "%s".') % (
                            step.name, workflow.name))

    @api.constrains('step_ids')
    def _check_notify_email_template(self):
        for workflow in self:
            for step in workflow.step_ids:
                if step.notify_assignee_email_on_enter and not step.email_template_assignee_enter:
                    raise ValidationError(
                        _('Email template for Assignee on Enter must be set for step "%s" in workflow "%s".') % (
                            step.name, workflow.name))

                if step.notify_leader_email_on_enter and not step.email_template_leader_enter:
                    raise ValidationError(
                        _('Email template for Leader on Enter must be set for step "%s" in workflow "%s".') % (
                            step.name, workflow.name))

                if step.notify_assignee_email_before_deadline and not step.email_template_assignee_deadline:
                    raise ValidationError(
                        _('Email template for Assignee before Deadline must be set for step "%s" in workflow "%s".') % (
                            step.name, workflow.name))

                if step.notify_leader_email_before_deadline and not step.email_template_leader_deadline:
                    raise ValidationError(
                        _('Email template for Leader before Deadline must be set for step "%s" in workflow "%s".') % (
                            step.name, workflow.name))
