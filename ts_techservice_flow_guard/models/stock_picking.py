from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _ts_get_picking_warehouse(self, location):
        warehouse = getattr(location, 'warehouse_id', False)
        if warehouse:
            return warehouse
        parent = getattr(location, 'location_id', False)
        while parent:
            warehouse = getattr(parent, 'warehouse_id', False)
            if warehouse:
                return warehouse
            parent = getattr(parent, 'location_id', False)
        return False

    def _ts_track_ticket_warehouse_flow(self, ticket):
        self.ensure_one()
        if not ticket:
            return
        source_wh = self._ts_get_picking_warehouse(self.location_id)
        dest_wh = self._ts_get_picking_warehouse(self.location_dest_id)
        vals = {}
        if self.picking_type_code == 'internal':
            if source_wh and not ticket.ts_source_warehouse_id:
                vals['ts_source_warehouse_id'] = source_wh.id
            if dest_wh:
                vals['ts_intermediate_warehouse_id'] = dest_wh.id
        elif self.picking_type_code == 'outgoing':
            if source_wh and not ticket.ts_target_warehouse_id:
                vals['ts_target_warehouse_id'] = source_wh.id
        if vals:
            ticket.write(vals)
        ticket._ts_create_audit_log(
            name='Đã ghi nhận luồng kho',
            change_scope='workflow',
            change_type='update',
            field_name='warehouse_flow',
            new_value='%s: %s -> %s' % (
                self.name or '',
                source_wh.display_name if source_wh else self.location_id.display_name,
                dest_wh.display_name if dest_wh else self.location_dest_id.display_name,
            ),
            reason=self.picking_type_code,
        )

    def button_validate(self):
        res = super().button_validate()
        for picking in self.filtered(lambda p: p.state == 'done'):
            sale = getattr(picking, 'sale_id', False)
            ticket = sale.ticket_id if sale and hasattr(sale, 'ticket_id') else False
            if not ticket:
                continue
            picking._ts_track_ticket_warehouse_flow(ticket)
            lots = picking.move_line_ids.filtered(lambda ml: ml.qty_done and ml.lot_id).mapped('lot_id')
            if picking.picking_type_code == 'outgoing' and lots:
                ticket._ts_apply_delivered_serial(lots[-1], source=picking.name)
        return res
