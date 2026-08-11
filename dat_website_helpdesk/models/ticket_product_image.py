import base64
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

class TicketProductImage(models.Model):
    _name = 'ticket.product.image'
    _description = "Ticket Product Image"
    _inherit = ['image.mixin']
    _order = 'sequence, id'

    name = fields.Char("Name", required=True)
    sequence = fields.Integer(default=10)

    image_1920 = fields.Image()

    ticket_id = fields.Many2one('ticket.helpdesk', "Ticket Helpdesk", index=True, ondelete='cascade')

    can_image_1024_be_zoomed = fields.Boolean("Can Image 1024 be zoomed", compute='_compute_can_image_1024_be_zoomed', store=True)

    @api.depends('image_1920', 'image_1024')
    def _compute_can_image_1024_be_zoomed(self):
        for image in self:
            image.can_image_1024_be_zoomed = image.image_1920 and tools.is_image_size_above(image.image_1920, image.image_1024)