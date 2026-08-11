from odoo import api, models


class AbstractCustomView(models.AbstractModel):
    """
    Abstract Model providing a framework for dynamically customizing Odoo views.

    This abstract model allows inheriting models to easily specify which fields
    or notebook pages should be hidden in their views (form, list, etc.)
    without directly modifying the XML view definitions.

    It works by overriding the `_get_view` method. When a view is requested,
    this model intercepts the process, checks the lists provided by the
    inheriting model's properties (`invisible_fields` and `invisible_form_pages`),
    and modifies the view's XML architecture (`arch`) on-the-fly to add
    `invisible="1"` or `column_invisible="1"` attributes where necessary.

    Usage:
        1. Inherit your model from 'abstract.custom.view'.
           Example: `_inherit = ['your.model', 'abstract.custom.view']`
        2. Override the `invisible_fields` property to return a set (or other
           iterable) of field names (strings) to hide.
        3. Override the `invisible_form_pages` property to return a set (or other
           iterable) of notebook page names (strings) to hide in form views.

    Example Override in an inheriting model:
        ```python
        @property
        def invisible_fields(self):
            # Hide 'field_to_hide_1' and 'field_to_hide_2'
            return {'field_to_hide_1', 'field_to_hide_2'}

        @property
        def invisible_form_pages(self):
            # Hide the notebook page named 'internal_details_page'
            return {'internal_details_page'}
        ```

    This approach centralizes view customization logic within the model's Python
    code, making it potentially more dynamic and easier to manage than
    hardcoding visibility in XML views. The `_set_view_item_attribute` helper
    ensures that existing `invisible="1"` attributes in the XML are respected
    and not overridden by this mechanism.
    """
    _name = 'abstract.custom.view'
    _description = 'Abstract Model for Custom Views in DAT System'

    @property
    def invisible_fields(self):
        return {}

    @property
    def readonly_fields(self):
        return {}

    @property
    def invisible_form_pages(self):
        return {}

    @property
    def invisible_form_buttons(self):
        return {}

    @api.model
    def _set_view_item_attribute(self, view_item, attr, val: bool):
        attr_val = view_item.attrib.get(attr)
        if attr_val not in ['1', 'True']:
            view_item.set(attr, str(val))

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        self._invisible_fields(arch)
        self._invisible_form_pages(arch)
        self._invisible_form_buttons(arch)

        self._set_readonly_fields(arch)
        return arch, view

    def _invisible_fields(self, arch):
        if not self.invisible_fields:
            return
        for field in arch.xpath("//field[not(ancestor::field)]"):
            self._handle_field_visibility(field)

    def _handle_field_visibility(self, field):
        name = field.attrib.get('name')
        if name in self.invisible_fields:
            self._set_invisible_attrs(field)
            return
        # Invisible nested fields (relational)
        field_obj = self._fields.get(name, None)
        if not self._is_relational_field(field_obj):
            return
        child_invisible_fields = getattr(
            self.env[field_obj.comodel_name], 'invisible_fields', set()
        )
        if not child_invisible_fields:
            return
        for sub_field in field.xpath(f"//field[ancestor::field[@name='{name}']]"):
            self._handle_nested_field_visibility(
                sub_field, child_invisible_fields)

    def _set_invisible_attrs(self, field):
        self._set_view_item_attribute(field, 'invisible', True)
        self._set_view_item_attribute(field, 'column_invisible', True)

    def _is_relational_field(self, field_obj):
        return field_obj and field_obj.type in ('many2one', 'one2many', 'many2many')

    def _handle_nested_field_visibility(self, sub_field, invisible_fields):
        sub_field_name = sub_field.get('name')
        if sub_field_name in invisible_fields:
            self._set_invisible_attrs(sub_field)

    def _invisible_form_pages(self, arch):
        for page in arch.xpath("//notebook//page"):
            name = page.attrib.get('name')
            if name not in self.invisible_form_pages:
                continue
            self._set_view_item_attribute(
                page, 'invisible', True)

    def _invisible_form_buttons(self, arch):
        for page in arch.xpath("//button"):
            name = page.attrib.get('name')
            if name not in self.invisible_form_buttons:
                continue
            self._set_view_item_attribute(
                page, 'invisible', True)

    def _set_readonly_attrs(self, field):
        self._set_view_item_attribute(field, 'readonly', True)

    def _set_readonly_fields(self, arch):
        if not self.readonly_fields:
            return
        for field in arch.xpath("//field[not(ancestor::field)]"):
            self._handle_field_readonly(field)

    def _handle_field_readonly(self, field):
        name = field.attrib.get('name')
        if name in self.readonly_fields:
            self._set_readonly_attrs(field)
            return
        # Set readonly for nested fields (relational)
        field_obj = self._fields.get(name, None)
        if not self._is_relational_field(field_obj):
            return
        child_readonly_fields = getattr(
            self.env[field_obj.comodel_name], 'readonly_fields', set()
        )
        if not child_readonly_fields:
            return
        for sub_field in field.xpath(f"//field[ancestor::field[@name='{name}']]"):
            self._handle_nested_field_readonly(
                sub_field, child_readonly_fields)

    def _is_relational_field(self, field_obj):
        return field_obj and field_obj.type in ('many2one', 'one2many', 'many2many')

    def _handle_nested_field_readonly(self, sub_field, readonly_fields):
        sub_field_name = sub_field.get('name')
        if sub_field_name in readonly_fields:
            self._set_readonly_attrs(sub_field)
