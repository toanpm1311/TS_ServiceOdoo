from odoo import api, fields, models


class NotificationTemplate(models.Model):
    _name = "notification.template"
    _inherit = 'mail.render.mixin'
    _description = 'Notification Template'
    _rec_name = 'title'

    title = fields.Char(required=True, translate=True)
    body = fields.Text(required=True)
    notification_type_id = fields.Many2one('notification.type')
    target_action = fields.Selection([
        ('open_detail_screen', 'Open Detail Screen'),
        ('open_list_screen', 'Open List Screen'),
    ], default='open_detail_screen')
    screen_type = fields.Selection([
        ('ticket_helpdesk', 'Ticket Helpdesk'),
    ])
    model_id = fields.Many2one('ir.model', 'Applies to')
    model = fields.Char('Related Model',
                        related='model_id.model', index=True, store=True, readonly=True, copy=True)

    # Overrides of mail.render.mixin
    @api.depends('model')
    def _compute_render_model(self):
        for template in self:
            template.render_model = template.model

    def generate_template_render_results(self, res_ids, render_fields, add_context=None, **kwargs):
        """ Return values based on template 'self'. Those are rendered of notifications.

        :param list res_ids: list of record IDs on which template is rendered;
        :param list render_fields: list of fields to render;
        :param dict add_context: dict of context was used in the notification body.
          For each res_id, a dict of values based on render_fields is given;

        :return: render_results;
        """

        self.ensure_one()
        add_context = add_context or {}
        if not self.model:
            return
        render_fields_set = set(render_fields)
        render_results = {}
        for field in render_fields_set:
            generated_field_values = self._render_field(
                field, res_ids, add_context=add_context
            )
            for res_id, field_value in generated_field_values.items():
                render_results.setdefault(res_id, {})[field] = field_value
        return render_results

    def send_notification(self, res_ids, add_context=None,  recipient_ids=None, current_action=None, **kwargs):
        """
        Send notification from template.
        Params:
        - res_ids: ids of records to create new notifications
        - add_context: Contains values used in template
        - kwargs: Contains fields overwrited in template
        """
        self.ensure_one()
        add_context = add_context or {}
        recipient_ids = recipient_ids or []
        temp_template = self.copy()
        temp_template.update(kwargs)
        render_fields = ['title', 'body']
        notifications = self.env['res.users.notification']
        for recipient_id in recipient_ids:
            recipient = self.env['res.partner'].browse(recipient_id)
            user = self.env['res.users'].search([('partner_id', '=', recipient.id)], limit=1)
            if current_action and not current_action.check_user_allowed_noti(user, temp_template.notification_type_id):
                continue
            add_context['recipient'] = recipient
            render_results = temp_template.generate_template_render_results(
                res_ids, render_fields, add_context, **kwargs)
            res_records = self.env[temp_template.model].browse(res_ids)
            for rec in res_records:
                payload = {
                    'in_app': True,
                    'notification_type_id': temp_template.notification_type_id.id if temp_template.notification_type_id else None,
                    'target_action': temp_template.target_action,
                    'screen_type': temp_template.screen_type,
                    'recipient_ids': [recipient.id or rec.user_id.partner_id.id],
                    'target_record': rec,
                }
                payload.update(render_results[rec.id])
                notifications = self.env.user.send_notification(**payload)
        temp_template.unlink()
        return notifications
