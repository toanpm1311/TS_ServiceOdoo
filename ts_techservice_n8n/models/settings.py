from urllib.parse import urlparse

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ts_n8n_url = fields.Char(
        string='Webhook n8n TechService',
        config_parameter='ts_techservice_n8n.webhook_url', groups='base.group_system',
    )
    ts_n8n_token = fields.Char(
        string='Token webhook n8n',
        config_parameter='ts_techservice_n8n.webhook_token', groups='base.group_system',
    )
    ts_n8n_holidays = fields.Char(
        string='Ngày nghỉ nhắc báo giá',
        help='Các ngày YYYY-MM-DD, ngăn cách bằng dấu phẩy. Không tính thứ Bảy, Chủ nhật.',
        config_parameter='ts_techservice_n8n.holidays', groups='base.group_system',
    )

    @api.constrains('ts_n8n_holidays', 'ts_n8n_url')
    def _check_ts_n8n_settings(self):
        for settings in self:
            try:
                for day in (settings.ts_n8n_holidays or '').split(','):
                    if day.strip():
                        fields.Date.to_date(day.strip())
            except ValueError as error:
                raise ValidationError(_('Ngày nghỉ phải có định dạng YYYY-MM-DD.')) from error
            if settings.ts_n8n_url:
                url = urlparse(settings.ts_n8n_url)
                if url.scheme != 'https' or not url.netloc:
                    raise ValidationError(_('Webhook n8n phải là URL HTTPS hợp lệ.'))
