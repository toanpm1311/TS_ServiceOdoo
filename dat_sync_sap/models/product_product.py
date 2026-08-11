from odoo import api, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        product_ids = list(super()._name_search(name, domain, operator, limit, order))
        domain = domain or []
        if not name or (limit and len(product_ids) >= limit):
            return product_ids

        positive_operators = ['=', 'ilike', '=ilike', 'like', '=like']
        if operator not in positive_operators:
            return product_ids

        remaining_limit = (limit - len(product_ids)) if limit else False
        exclude_domain = [('id', 'not in', product_ids)] if product_ids else []
        template_code_domains = [
            [('default_code', operator, name)],
            [('product_tmpl_id.default_code', operator, name)],
            [('name', operator, name)],
            [('product_tmpl_id.name', operator, name)],
            [('barcode', operator, name)],
            [('sap_model', operator, name)],
            [('sap_code_po', operator, name)],
            [('sap_serial_num', operator, name)],
            [('product_tmpl_id.sap_model', operator, name)],
            [('product_tmpl_id.sap_code_po', operator, name)],
            [('product_tmpl_id.sap_serial_num', operator, name)],
        ]
        if operator in ('=', '=ilike'):
            template_code_domains.append([('default_code', '=ilike', '%s%%' % name)])
            template_code_domains.append([('product_tmpl_id.default_code', '=ilike', '%s%%' % name)])
            template_code_domains.append([('sap_model', '=ilike', '%s%%' % name)])
            template_code_domains.append([('sap_code_po', '=ilike', '%s%%' % name)])
            template_code_domains.append([('sap_serial_num', '=ilike', '%s%%' % name)])
            template_code_domains.append([('product_tmpl_id.sap_model', '=ilike', '%s%%' % name)])
            template_code_domains.append([('product_tmpl_id.sap_code_po', '=ilike', '%s%%' % name)])
            template_code_domains.append([('product_tmpl_id.sap_serial_num', '=ilike', '%s%%' % name)])

        for code_domain in template_code_domains:
            extra_ids = list(self._search(domain + exclude_domain + code_domain, limit=remaining_limit, order=order))
            product_ids.extend(extra_ids)
            if limit and len(product_ids) >= limit:
                break
            remaining_limit = (limit - len(product_ids)) if limit else False
            exclude_domain = [('id', 'not in', product_ids)] if product_ids else []
        return product_ids
