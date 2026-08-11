from datetime import datetime
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrEmployeePrivate(models.Model):
    _name = 'hr.employee'
    _inherit = ['hr.employee', 'abstract.sync.sap']

    @property
    def api_route(self):
        return '/Users'

    @property
    def fields_mapping(self):
        """
        Provides the mapping between SAP Item API field names and Odoo fields.
        """
        return {
            'HRCode': 'sap_hr_code',
            'SlpCode': 'sap_slp_code',
            'FullName': 'name',
            'Title': 'job_title',
            'PositionHR': 'sap_position_hr',
            'DepartmentHR': 'sap_department_hr',
            'EmpPhone': 'mobile_phone',
            'Email': 'work_email',
            'WorkShift': 'sap_work_shift',
            'BusinessArea': 'sap_business_area',
            'Branch': 'sap_branch',
            'UserName': 'sap_user_name',
            'UpdateDate': 'sap_update_date',
        }

    @property
    def identify_fields(self):
        return {'sap_hr_code'}

    @property
    def period_cron_xml_id(self):
        return 'dat_sync_sap.ir_cron_sync_sap_user'

    @api.model
    def action_sync_salesperson_sap_metadata(self):
        self = self.sudo()
        sap_rows = self.get_all_sap_records()
        # Keep rows with an empty SlpCode as well. SAP uses an empty value when
        # a salesperson code is removed/reassigned, so skipping these rows
        # leaves the old code on the former employee and creates duplicates.
        employee_rows = [row for row in sap_rows if row.get('HRCode')]

        updated_count = 0
        affected_slp_codes = set()
        missing_hr_codes = []
        source_slp_owners = {}
        duplicate_source_slp_codes = set()
        for row in employee_rows:
            hr_code = self.clean_odoo_field_value('sap_hr_code', row.get('HRCode'))
            employee = self.search([('sap_hr_code', '=', hr_code)], limit=1)
            if not employee:
                missing_hr_codes.append(hr_code)
                continue
            old_slp_code = employee.sap_slp_code
            vals = {}
            for sap_field in ('FullName', 'SlpCode', 'BusinessArea'):
                if sap_field not in row:
                    continue
                odoo_field = self.fields_mapping[sap_field]
                value = self.clean_odoo_field_value(odoo_field, row.get(sap_field))
                if odoo_field == 'sap_slp_code' and value in (None, False, '', 'null'):
                    value = False
                vals[odoo_field] = value
            if vals:
                employee.with_context(skip_slp_partner_recompute=True).write(vals)
                affected_slp_codes.update(
                    code for code in (old_slp_code, employee.sap_slp_code) if code
                )
                updated_count += 1

            slp_code = employee.sap_slp_code
            if slp_code:
                previous_owner = source_slp_owners.get(slp_code)
                if previous_owner and previous_owner != employee:
                    duplicate_source_slp_codes.add(slp_code)
                else:
                    source_slp_owners[slp_code] = employee

        # Treat the full /Users response as authoritative for Slp ownership.
        # If SAP assigns a code to a new employee but omits the former owner,
        # remove that code from every stale Odoo employee explicitly.
        for slp_code, owner in source_slp_owners.items():
            if slp_code in duplicate_source_slp_codes:
                continue
            stale_employees = self.search([
                ('sap_slp_code', '=', slp_code),
                ('id', '!=', owner.id),
            ])
            if stale_employees:
                stale_employees.with_context(skip_slp_partner_recompute=True).write({
                    'sap_slp_code': False,
                })
                affected_slp_codes.add(slp_code)

        if affected_slp_codes:
            partners = self.env['res.partner'].sudo().search([
                ('sap_slp_code', 'in', list(affected_slp_codes)),
            ])
            partners._compute_sale_person()

        _logger.info(
            "SAP salesperson metadata sync done | source_rows=%s | updated=%s | missing_hr_codes=%s | duplicate_source_slp_codes=%s",
            len(employee_rows),
            updated_count,
            missing_hr_codes,
            sorted(duplicate_source_slp_codes),
        )
        return True

    def clean_odoo_field_value(self, fname: str, value):
        value = super().clean_odoo_field_value(fname, value)
        if fname == 'sap_hr_code' and value not in (None, False, ''):
            value = str(value).strip()
            if value.isdigit():
                value = value.zfill(4)
        elif fname == 'sap_slp_code':
            if value in (None, False, '', 'null'):
                value = False
            elif isinstance(value, str):
                value = value.strip()
                if value.isdigit():
                    value = int(value)
        elif fname == 'name' and not value:
            # SAP Items can have not name
            value = ' '
        elif fname == 'mobile_phone' and value:
            value = value.strip()
            value = value.replace(' ', '').replace('-', '')
            if (not value.startswith(('0', '(', '+')) and len(value) < 10):
                value = '0' + value
            if not value.lstrip('(+').replace(')', '').isdigit():
                value = ''
        return value

    def action_sync_current_employee_from_sap(self):
        """Refresh the current employee, matching by HR code or work email."""
        self.ensure_one()
        employee = self.sudo()
        sap_rows = employee.get_all_sap_records()

        hr_code = (employee.sap_hr_code or '').strip()
        work_email = (employee.work_email or '').strip().lower()
        matching_row = False

        if hr_code:
            normalized_hr_code = employee.clean_odoo_field_value('sap_hr_code', hr_code)
            matching_row = next(
                (
                    row for row in sap_rows
                    if employee.clean_odoo_field_value('sap_hr_code', row.get('HRCode'))
                    == normalized_hr_code
                ),
                False,
            )

        if not matching_row and work_email:
            matching_row = next(
                (
                    row for row in sap_rows
                    if (row.get('Email') or '').strip().lower() == work_email
                ),
                False,
            )

        if not matching_row:
            raise UserError(_(
                "Không tìm thấy nhân viên tương ứng trên SAP. "
                "Vui lòng kiểm tra SAP Mã HR hoặc Email công việc."
            ))

        values = {}
        for sap_field, odoo_field in employee.fields_mapping.items():
            if sap_field in matching_row:
                values[odoo_field] = employee.clean_odoo_field_value(
                    odoo_field, matching_row.get(sap_field)
                )
        employee.write(values)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đồng bộ SAP'),
                'message': _('Đã cập nhật dữ liệu nhân viên từ SAP.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def write(self, vals):
        old_slp_codes = set(self.mapped('sap_slp_code')) if 'sap_slp_code' in vals else set()
        res = super().write(vals)
        if 'sap_branch' in vals:
            self._compute_company_id()
        if 'sap_position_hr' in vals or 'sap_department_hr' in vals or 'company_id' in vals:
            self._compute_department_id()
        if 'sap_slp_code' in vals and not self.env.context.get('skip_slp_partner_recompute'):
            affected_codes = old_slp_codes | set(self.mapped('sap_slp_code'))
            affected_codes.discard(False)
            if affected_codes:
                partners = self.env['res.partner'].sudo().search([
                    ('sap_slp_code', 'in', list(affected_codes)),
                ])
                partners._compute_sale_person()
        return res
