# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import pandas as pd
import io


class QuotationProductImportWizard(models.TransientModel):
    _name = 'quotation.product.import.wizard'
    _description = 'Import Products for Quotation'

    DEFAULT_CODE_COL = 'Default Code'

    file = fields.Binary(string='Upload File')
    file_name = fields.Char(string='File Name')

    def import_product_data(self):
        order = self._get_active_order()
        df = self._load_products_sheet()
        existing = self._fetch_existing_codes(df)
        self._assert_all_codes_exist(df, existing)
        lines = self._build_order_lines(df, existing, order)
        self._create_order_lines(lines)
        return self._action_return_form(order.id)

    def _get_active_order(self):
        order = self.env['sale.order'].browse(self._context.get('active_id'))
        if not order:
            raise UserError(_('No active quotation found.'))
        return order

    def _load_products_sheet(self):
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

        try:
            return pd.read_excel(io.BytesIO(data), sheet_name='Products')
        except Exception as e:
            raise UserError(_('Error reading Excel file: %s') % e)

    def _fetch_existing_codes(self, df):
        col = _(self.DEFAULT_CODE_COL)
        if col not in df.columns:
            raise UserError(_('Excel sheet is missing column: %s') % col)

        raw_codes = df[col].dropna()
        codes = {str(c).strip().upper() for c in raw_codes}

        products = self.env['product.product'].search([
            ('default_code', 'in', list(codes))
        ])
        return {
            p.default_code.strip().upper(): p.id
            for p in products
        }

    def _assert_all_codes_exist(self, df, existing):
        raw_codes = df.get(_(self.DEFAULT_CODE_COL))
        sheet_codes = {str(c).strip().upper() for c in raw_codes.dropna()}
        missing = sheet_codes - existing.keys()
        if missing:
            raise UserError(
                _('Invalid Default Codes in file: %s') % ', '.join(sorted(missing))
            )

    def _build_order_lines(self, df, existing, order):
        def parse_num(val, default):
            return float(val) if isinstance(val, (int, float)) and not pd.isna(val) else default

        prices_by_code = self._fetch_price_by_code(existing.keys(), order)
        lines = []
        for idx, row in df.iterrows():
            code = str(row.get(_(self.DEFAULT_CODE_COL), '')).strip().upper()
            line_values = {
                'order_id': order.id,
                'product_id': existing[code],
                'product_uom_qty': parse_num(row.get(_('Quantity')), 1),
            }
            if code in prices_by_code:
                line_values['price_unit'] = prices_by_code[code]
            lines.append(line_values)
        return lines

    def _fetch_price_by_code(self, codes, order):
        SaleOrderLine = self.env['sale.order.line']
        price_items = SaleOrderLine._get_dat_price_items(
            codes, order.company_id or self.env.company
        )
        prices_by_code = {}
        for item_code, price_item in price_items.items():
            target_currency = order.currency_id
            price = price_item.price
            if target_currency and price_item.currency_id != target_currency:
                price = price_item.currency_id._convert(
                    price,
                    target_currency,
                    order.company_id or self.env.company,
                    fields.Date.to_date(order.date_order)
                    or fields.Date.context_today(self),
                    round=False,
                )
            prices_by_code[item_code] = price
        return prices_by_code

    def _create_order_lines(self, lines):
        if lines:
            self.env['sale.order.line'].create(lines)

    def _action_return_form(self, order_id):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': order_id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_export_products(self):
        columns = [
            _('Default Code'), _('Product Name'), _('Quantity'), _('Unit Price'), _('Description')
        ]
        data = []
        df = pd.DataFrame(data, columns=columns)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Products', index=False)
        excel_data = output.getvalue()

        attachment = self.env['ir.attachment'].create({
            'name': 'product_template.xlsx',
            'datas': base64.b64encode(excel_data),
            'type': 'binary',
            'res_model': 'sale.order',
            'res_id': self._context.get('active_id'),
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
