from odoo import _, models

SYNC_MODELS = [
    'product.category',
    'uom.uom',
    'product.template',
    'resource.calendar.attendance',
    'hr.employee',
    'res.partner',
    'stock.lot',
]


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_sync_sap_all(self):
        for model in [m for m in SYNC_MODELS if m != 'stock.lot']:
            self.env[model].sync_sap_data()
            self.env.cr.commit()

    def action_sync_sap_specific_model(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sync SAP Specific Data'),
            'res_model': 'sync.specific.model.wizard',
            'view_mode': 'form',
            'target': 'new',
            'views': [[False, 'form']],
            'context': {
                'dialog_size': 'extra-large',
            },
        }
