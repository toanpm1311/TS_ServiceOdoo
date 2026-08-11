from odoo import _, fields, models, api
from odoo.exceptions import UserError
from odoo.addons.dat_sap_config.tools.datetime import format_datetime_object
import pytz
from datetime import datetime
from ..models.res_config_settings import SYNC_MODELS


class SyncSpecificModelWizard(models.TransientModel):
    _name = "sync.specific.model.wizard"
    _description = "Sync Specific Model Wizard"

    def _default_model_name_selection(self):
        return [
            (model, self.env[model]._description) for model in SYNC_MODELS
        ]

    model_name = fields.Selection(selection=_default_model_name_selection)
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")

    def action_sync_sap_specific_model(self):
        tz = pytz.timezone('Asia/Ho_Chi_Minh')
        if self.start_date:
            start_dt = datetime.combine(self.start_date, datetime.min.time())
        if self.end_date:
            end_dt = datetime.combine(self.end_date, datetime.max.time())
        if self.model_name == 'stock.lot' and (self.start_date or self.end_date):
            if not self.start_date or not self.end_date:
                raise UserError(_("Please select both Start Date and End Date to sync Stock Lot."))
            params = {
                "PageNumber": 1,
                "PageSize": 1000,
            }
            params["ModifiedDateStart"] = format_datetime_object(
                                        dt_object=start_dt,
                                        tz_from=pytz.utc,
                                        tz_to=tz,
                                        format_to='%Y-%m-%dT%H:%M:%S'
                                    )
            params["ModifiedDateEnd"] = format_datetime_object(
                                        dt_object=end_dt,
                                        tz_from=pytz.utc,
                                        tz_to=tz,
                                        format_to='%Y-%m-%dT%H:%M:%S'
                                    )
            self.env[self.model_name].sync_sap_data(json_data=params)
            return
        if self.model_name == 'res.partner' and (self.start_date or self.end_date):
            self.env[self.model_name].sync_sap_data(
                start_dt=start_dt if self.start_date else None,
                end_dt=end_dt if self.end_date else None
            )
            return
        if self.model_name == 'stock.lot':
            raise UserError(_("Please select Start Date and End Date to sync Stock Lot."))
        else:
            self.env[self.model_name].sync_sap_data()
