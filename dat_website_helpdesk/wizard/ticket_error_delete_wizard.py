from odoo import models, fields, api, _
from odoo.exceptions import UserError

class TicketErrorDeleteWizard(models.TransientModel):
    _name = 'ticket.error.delete.wizard'
    _description = 'Delete Error Confirmation Wizard'

    error_id = fields.Many2one(
        'ticket.helpdesk.error',
        string='Errors to Delete',
        readonly=True,
    )
    message = fields.Text(
        string='Confirmation Message',
        default=lambda self: _('Bạn có chắc chắn muốn xóa nhật ký hiện trường đã chọn không? Thao tác này không thể hoàn tác.'),
        readonly=True,
    )

    def action_confirm_delete(self):
        """
        Confirm and delete the selected error records.
        """
        if not self.error_id:
            raise UserError(_('No errors selected to delete.'))
        self.error_id.unlink()
        return {
            'type': 'ir.actions.act_window_close',
        }

    def action_cancel(self):
        """
        Cancel deletion.
        """
        return {
            'type': 'ir.actions.act_window_close',
        }