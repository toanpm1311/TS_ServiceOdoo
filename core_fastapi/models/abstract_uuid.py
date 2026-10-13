from uuid import uuid4

from psycopg2 import sql

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL


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
        result = super()._auto_init()
        if self._abstract:
            return result

        table = SQL.identifier(self._table)
        update_query = sql.SQL("""
            UPDATE {} AS record
               SET uuid = source.uuid
              FROM (VALUES %s) AS source(id, uuid)
             WHERE record.id = source.id
        """).format(sql.Identifier(self._table))
        while True:
            self.env.cr.execute(SQL(
                "SELECT id FROM %s WHERE uuid IS NULL LIMIT %s",
                table,
                1000,
            ))
            record_ids = [row[0] for row in self.env.cr.fetchall()]
            if not record_ids:
                break
            self.env.cr.execute_values(
                update_query,
                [(record_id, str(uuid4())) for record_id in record_ids],
            )
        return result

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
