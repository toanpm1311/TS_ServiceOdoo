from odoo import fields, models


class MailComposeMessage(models.TransientModel):
    """Inheriting the Mail compose message"""
    _inherit = 'mail.compose.message'

    def _action_send_mail(self, auto_commit=False):
        """Send mail function"""
        if self.model == 'ticket.helpdesk':
            try:
                res_ids_list = eval(self.res_ids)
                if not isinstance(res_ids_list, list):
                    raise ValueError("Invalid format for res_ids")
            except Exception as e:
                raise ValueError(
                    "Error converting res_ids to list: {}".format(e))
            ticket_ids = self.env['ticket.helpdesk'].browse(res_ids_list)
            ticket_ids.replied_date = fields.Date.today()
        return super(MailComposeMessage, self)._action_send_mail(
            auto_commit=auto_commit)
