# -*- coding: utf-8 -*-

import base64
import io
import re

try:
    import xlrd
except ImportError:
    xlrd = None

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

from odoo import fields, models, _
from odoo.exceptions import UserError


class DatPriceListImportWizard(models.TransientModel):
    _name = 'dat.price.list.import.wizard'
    _description = 'Import DAT Price List'

    CODE_ALIASES = ('item code', 'default code', 'invt code', 'inv t code', 'inventory code')
    PRICE_ALIASES = ('price', 'unit price', 'end user', 'end user before vat', 'before vat')
    DESCRIPTION_ALIASES = ('description', 'product name', 'name')

    file = fields.Binary(string='Upload File')
    file_name = fields.Char(string='File Name')
    update_existing = fields.Boolean(string='Update Existing Items', default=True)

    def action_import(self):
        self.ensure_one()
        df = self._load_excel()
        header_index, columns = self._detect_columns(df)
        lines = self._prepare_lines(df, header_index, columns)
        created, updated = self._upsert_lines(lines)
        return self._show_result(created, updated)

    def _load_excel(self):
        if not self.file or not self.file_name:
            raise UserError(_('Please upload an Excel file.'))

        fname = self.file_name.lower()
        if not fname.endswith(('.xls', '.xlsx', '.xlsm', '.xlsb')):
            raise UserError(_('Invalid file type: %s. Please upload a .xls/.xlsx file.') % self.file_name)

        try:
            data = base64.b64decode(self.file)
        except Exception:
            raise UserError(_('Could not decode the uploaded file.'))

        header = data[:4]
        is_xlsx = header[:2] == b'PK'
        is_xls = header == b'\xD0\xCF\x11\xE0'
        if not (is_xlsx or is_xls):
            raise UserError(_('The file %s does not appear to be a valid Excel file.') % self.file_name)

        if not xlrd:
            raise UserError(_('Missing Python library xlrd to read Excel files.'))

        try:
            workbook = xlrd.open_workbook(file_contents=data)
            sheet = workbook.sheet_by_index(0)
            return [
                [self._get_cell_value(sheet.cell(row_index, col_index)) for col_index in range(sheet.ncols)]
                for row_index in range(sheet.nrows)
            ]
        except Exception as error:
            raise UserError(_('Error reading Excel file: %s') % error)

    def _detect_columns(self, rows):
        for row_index, row in enumerate(rows):
            normalized_cells = [self._normalize(value) for value in row]
            code_col = self._find_column(normalized_cells, self.CODE_ALIASES)
            price_col = self._find_column(normalized_cells, self.PRICE_ALIASES)
            if code_col is not None and price_col is not None:
                return row_index, {
                    'code': code_col,
                    'price': price_col,
                    'description': self._find_column(normalized_cells, self.DESCRIPTION_ALIASES),
                }
        raise UserError(_('Could not find Item Code and Price columns in the Excel file.'))

    def _prepare_lines(self, rows, header_index, columns):
        lines_by_code = {}
        for row_index, row in enumerate(rows[header_index + 1:], start=header_index + 2):
            item_code = self._clean_text(self._get_row_value(row, columns['code'])).upper()
            if not item_code:
                continue

            price = self._parse_price(self._get_row_value(row, columns['price']), row_index)
            description = ''
            if columns.get('description') is not None:
                description = self._clean_text(self._get_row_value(row, columns['description']))

            lines_by_code[item_code] = {
                'item_code': item_code,
                'description': description,
                'price': price,
            }

        if not lines_by_code:
            raise UserError(_('No price list items were found in the Excel file.'))
        return list(lines_by_code.values())

    def _upsert_lines(self, lines):
        PriceItem = self.env['dat.price.list.item'].with_context(active_test=False)
        company = self.env.company
        currency = company.currency_id
        created = updated = 0

        existing_items = PriceItem.search([
            ('item_code', 'in', [line['item_code'] for line in lines]),
            ('company_id', '=', company.id),
        ])
        existing_by_code = {item.item_code: item for item in existing_items}

        for line in lines:
            item = existing_by_code.get(line['item_code'])
            vals = {
                'description': line['description'],
                'price': line['price'],
                'currency_id': currency.id,
                'company_id': company.id,
                'active': True,
            }
            if item:
                if self.update_existing:
                    item.write(vals)
                    updated += 1
                continue

            vals['item_code'] = line['item_code']
            PriceItem.create(vals)
            created += 1

        return created, updated

    def _show_result(self, created, updated):
        message = _('Import completed. Created: %(created)s. Updated: %(updated)s.') % {
            'created': created,
            'updated': updated,
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Price List Import'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_export_template(self):
        if not xlsxwriter:
            raise UserError(_('Missing Python library xlsxwriter to export Excel files.'))

        columns = [_('Item Code'), _('Description'), _('Price')]
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Price List')
        for col_index, column in enumerate(columns):
            sheet.write(0, col_index, column)
        workbook.close()

        attachment = self.env['ir.attachment'].create({
            'name': 'price_list_template.xlsx',
            'datas': base64.b64encode(output.getvalue()),
            'type': 'binary',
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def _find_column(self, cells, aliases):
        for index, cell in enumerate(cells):
            if any(alias in cell for alias in aliases):
                return index
        return None

    def _normalize(self, value):
        text = self._clean_text(value).lower()
        return re.sub(r'[^a-z0-9]+', ' ', text).strip()

    def _clean_text(self, value):
        if value in (None, False, ''):
            return ''
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    def _parse_price(self, value, row_number):
        if value in (None, False, ''):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip().replace(',', '')
        try:
            return float(text)
        except ValueError:
            raise UserError(_('Invalid price at row %s: %s') % (row_number, value))

    def _get_cell_value(self, cell):
        if xlrd and cell.ctype == xlrd.XL_CELL_EMPTY:
            return ''
        return cell.value

    def _get_row_value(self, row, index):
        if index is None or index >= len(row):
            return ''
        return row[index]
