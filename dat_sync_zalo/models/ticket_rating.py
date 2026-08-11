from datetime import datetime

from odoo import api, models


class TicketRating(models.Model):
    _name = 'ticket.rating'
    _inherit = ['ticket.rating', 'abstract.sync.zalo']

    @property
    def api_route(self):
        return '/rating/get'

    @property
    def fields_mapping(self):
        """
        Provides the mapping between ZALO Item API field names and Odoo fields.
        """
        return {
            'note': 'note',
            'rate': 'rate',
            'submitDate': 'submit_dt',
            'msgId': 'zalo_msg_ref',
            'feedbacks': 'feedbacks',
            'trackingId': 'zalo_tracking_id',
        }

    @property
    def identify_fields(self):
        return {'zalo_msg_ref'}

    @property
    def period_cron_xml_id(self):
        return 'dat_sync_zalo.ir_cron_sync_zalo_feedback'

    def clean_odoo_field_value(self, fname: str, value):
        value = super().clean_odoo_field_value(fname, value)
        if fname == 'submit_dt':
            value = datetime.fromtimestamp(int(value) / 1000)
        return value

    def write(self, vals):
        res = super().write(vals)
        if 'zalo_msg_ref' in vals:
            self._compute_zalo_msg_id()
        return res

    @api.model_create_multi
    def create(self, vals):
        records = super().create(vals)
        records._compute_zalo_msg_id()
        return records

    @api.model
    def prepare_params_for_period_sync_zalo(self, start_dt: datetime, end_dt: datetime):
        json_data = super().prepare_params_for_period_sync_zalo(start_dt, end_dt)
        config_model = self.env['ir.config_parameter'].sudo()
        offset = config_model.get_param(
            'dat_sync_zalo.zalo_default_param_offset')
        limit = config_model.get_param(
            'dat_sync_zalo.zalo_default_param_limit')
        fb_template_id = config_model.get_param(
            'dat_sync_zalo.zalo_feedback_template_id')
        json_data.update({
            'offset': offset,
            'limit': limit,
            'template_id': fb_template_id
        })
        return json_data
