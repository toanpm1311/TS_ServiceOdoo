import base64
import io

from odoo import api, fields, models, _
from odoo.modules.module import get_module_resource


class CommonUtilsMixin(models.AbstractModel):
    _name = 'common.utils.mixin'
    _description = 'Common Utilities Mixin'

    @api.model
    def get_record_selection_label(self, record, field_name):
        """
        Return the translated label for a selection field on *any* record.
        This method will look up record._fields[field_name] and use that
        record’s env to get the translation.
        """
        if not record or field_name not in record._fields:
            return ''
        # build dict from the target record’s field
        sel = dict(record._fields[field_name]
                   ._description_selection(record.env))
        raw = getattr(record, field_name)
        return sel.get(raw, raw) if raw else ''

    @api.model
    def float_to_time_string(self, hours_float, sep=":"):
        """
        Convert a decimal number of hours into a string "H{sep}MM".

        Example:
            1.5   -> "1:30"
            2.25  -> "2:15"
            0.333 -> "0:20"
        """
        # Ensure non-negative
        total_minutes = max(0, hours_float) * 60
        h = int(total_minutes // 60)
        m = int(round(total_minutes % 60))
        # handle edge case where round pushes minutes to 60
        if m == 60:
            h += 1
            m = 0
        return f"{h}{sep}{m:02d}"

    @api.model
    def convert_to_user_tz(self, utc_dt):
        """
        Given a UTC datetime, return a datetime in the current user’s timezone.
        If utc_dt is False/None, returns ''.
        """
        if not utc_dt:
            return ''
        # fields.Datetime.context_timestamp will read the user's tz from the context
        local_dt = fields.Datetime.context_timestamp(self, utc_dt)
        return local_dt

    def _get_xlsx_report_company(self):
        self.ensure_one()
        return (
            getattr(self, 'company_id', False)
            or getattr(self, 'branch_id', False)
            or getattr(self, 'branch', False)
            or self.env.company
        )

    def _get_xlsx_report_logo(self, company=False):
        logo_path = get_module_resource(
            'dat_website_helpdesk', 'static', 'src', 'img', 'logo.png'
        )
        if logo_path:
            with open(logo_path, 'rb') as logo_file:
                return io.BytesIO(logo_file.read())

        companies = (
            company,
            self.env.ref('base.main_company', raise_if_not_found=False),
            self.env.company,
        )
        for candidate in companies:
            if candidate and candidate.sudo().logo:
                logo = candidate.sudo().logo
                if isinstance(logo, str):
                    logo = logo.encode()
                return io.BytesIO(base64.b64decode(logo))

        fallback_logo_path = get_module_resource(
            'dat_website_helpdesk', 'static', 'src', 'img', 'dat-color.png'
        )
        if not fallback_logo_path:
            return False
        with open(fallback_logo_path, 'rb') as logo_file:
            return io.BytesIO(logo_file.read())

    def _write_xlsx_report_header(self, workbook, sheet, title, column_count, filters=None):
        company = self._get_xlsx_report_company()
        last_col = max(column_count - 1, 3)
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'font_color': '#173B56',
            'align': 'center',
            'valign': 'vcenter',
        })
        company_format = workbook.add_format({
            'bold': True,
            'font_size': 10,
            'font_color': '#5D6D7E',
            'align': 'center',
            'valign': 'vcenter',
        })
        filter_label_format = workbook.add_format({
            'bold': True,
            'font_color': '#173B56',
            'bg_color': '#EAF4F8',
            'border': 1,
            'valign': 'vcenter',
        })
        filter_value_format = workbook.add_format({
            'font_color': '#243746',
            'border': 1,
            'valign': 'vcenter',
        })
        header_format = workbook.add_format({
            'bold': True,
            'font_color': '#FFFFFF',
            'bg_color': '#00A3E0',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
        })

        sheet.hide_gridlines(2)
        sheet.freeze_panes(5 + len(filters or []), 0)
        sheet.set_row(0, 48)
        logo = self._get_xlsx_report_logo(company)
        if logo:
            sheet.insert_image('A1', 'dat_logo.png', {
                'image_data': logo,
                'x_scale': 0.30,
                'y_scale': 0.30,
                'x_offset': 4,
                'y_offset': 4,
            })
        else:
            sheet.write(0, 0, 'DAT', title_format)

        sheet.merge_range(0, 1, 0, last_col, title, title_format)
        sheet.merge_range(1, 1, 1, last_col, company.display_name or _('DAT Group'), company_format)

        row = 3
        for label, value in filters or []:
            sheet.write(row, 0, label, filter_label_format)
            sheet.merge_range(row, 1, row, last_col, value or '', filter_value_format)
            row += 1

        header_row = row + 1
        return header_row, header_format
