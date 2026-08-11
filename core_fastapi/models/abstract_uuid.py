from uuid import uuid4

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AbstractUUID(models.AbstractModel):
    _name = 'abstract.uuid'
    _description = 'This abstract model defines the uuid for related models.'

    uuid = fields.Char(
        readonly=True,
        help='Alternate way to identify a record, used for access records from apis.',
        copy=False)

    _sql_constraints = [
        ("uuid_unique", "unique(uuid)", "The UUID must be unique."),
    ]

    def _auto_init(self):
        super()._auto_init()
        # set uuid for the existing records
        try:
            if not self._abstract:
                self.env.cr.execute("""
                    UPDATE %s SET uuid=gen_random_uuid() WHERE id is not null and uuid is null
                """ % self._table)
        except Exception:
            self.env.cr.rollback()

    def browse_by_uuid(self, uuid: str):
        return self.search([('uuid', '=', uuid)], limit=1)

    def browse_by_uuids(self, uuids: list[str]):
        return self.search([('uuid', 'in', uuids)])

    def browse_by_primary_fields(self, **kwargs):
        """
        Overwrite this function in model containing multi the primary key
        """
        return self

    def validate_by_uuid(self, uuid: str):
        rec = self.browse_by_uuid(uuid)
        if not rec:
            raise UserError(_("Record not found for %s.") % self._description)
        return rec

    def validate_by_uuids(self, uuids: list[str]):
        rec = self.browse_by_uuids(uuids)
        if not rec:
            raise UserError(_("Record not found for %s.") % self._description)
        return rec

    def prepare_instance_creation_vals(self, vals):
        """
        Prepares creation values for an instance
        """
        # add default value for uuid field
        vals['uuid'] = str(uuid4())
        return vals

    def prepare_creation_vals_list(self, vals_list):
        for vals in vals_list:
            vals = self.prepare_instance_creation_vals(vals)
        return vals_list

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = self.prepare_creation_vals_list(vals_list)
        res = super().create(vals_list)
        return res
