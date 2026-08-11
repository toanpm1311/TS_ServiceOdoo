from odoo import _, api, fields, models
from odoo.exceptions import UserError

SAP_PRODUCT_CATEGORY_FIELDS = {
    'name',
    'sap_code',
    'display_name',
    'sap_product_line',
    'sap_product_family',
    'sap_brand',
    'sap_business_unit',
    'parent_id',
}


class ProductCategory(models.Model):
    """
    Odoo fields was used for SAP includes:
    - name: ItemName
    - sap_code: ItmsGrpCod
    - sap_product_line: U_ProductLine
    - sap_product_family: U_ProductFamily
    - sap_brand: U_Brand
    - sap_business_unit: U_BusinessUnit
    """
    _name = 'product.category'
    _inherit = ['product.category', 'abstract.custom.view']
    _description = 'Product Group'

    # SAP fields
    sap_code = fields.Integer("Code", default=False)
    sap_product_line = fields.Char("Product Line")
    sap_product_family = fields.Char("Product Family")
    sap_brand = fields.Char("Brand")
    sap_business_unit = fields.Char("Business Unit")

    _sql_constraints = [
        ("sap_code_uniq", "unique(sap_code)",
         _("Group Code is unique!")),
    ]

    @property
    def invisible_fields(self):
        return self._fields.keys() - SAP_PRODUCT_CATEGORY_FIELDS

    def check_access_rights(self, operation, raise_exception=True):
        if operation != 'read':
            return False
        return super().check_access_rights(operation, raise_exception)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_default_category(self):
        default_category = self.env.ref(
            'dat_product.product_category_default', raise_if_not_found=False)
        if default_category and default_category in self:
            raise UserError(
                _("You cannot delete this product category, it is the default generic category."))
