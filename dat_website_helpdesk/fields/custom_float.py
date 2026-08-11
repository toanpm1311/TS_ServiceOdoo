# -*- coding: utf-8 -*-
from odoo import fields
from odoo.fields import Float as BaseFloat

class CustomFloat(BaseFloat):
    """
    Custom Float field that truly has NO default (neither Python nor DB),
    so in the form it starts blank—and if required=True, the user must fill it.
    """
    _type = 'float'
    description = "Float required to input (no default)"
    column_default = False

    def __init__(self, string=None, digits=None, default=None, **kwargs):
        explicit_default = default
        super().__init__(string=string, digits=digits, default=None, **kwargs)
        if explicit_default is not None:
            self.default = explicit_default
        self.column_default = False

    def convert_to_cache(self, value, record=None, validate=True):
        if value in (None, ''):
            return None
        return super().convert_to_cache(value, record=record, validate=validate)

    def convert_to_column(self, value, record, values=None, validate=True):
        if value in (None, ''):
            return None
        return super().convert_to_column(value, record, values=values, validate=validate)

    def convert_to_record(self, value, record):
        return value
