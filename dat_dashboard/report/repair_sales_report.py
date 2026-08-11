from odoo import api, fields, models, tools

class RepairSalesReport(models.Model):
    _name = 'repair.sales.report'
    _description = 'Repair Sales Report'
    _auto = False

    date_order      = fields.Datetime('Date', readonly=True)
    ticket_id       = fields.Many2one('ticket.helpdesk', 'Ticket', readonly=True)
    order_id        = fields.Many2one('sale.order',   'Sales Order', readonly=True)
    product_code    = fields.Char('Product Code', readonly=True)
    product_name    = fields.Char('Product Name', readonly=True)
    product_uom = fields.Many2one('uom.uom', 'UoM', readonly=True)
    product_uom_qty = fields.Float('Quantity', readonly=True)
    price_unit      = fields.Float('Unit Price', readonly=True)
    price_total     = fields.Float('Total', readonly=True)
    customer_id     = fields.Many2one('res.partner','Customer', readonly=True)
    sale_person_id  = fields.Many2one('hr.employee',  'Salesperson', readonly=True)
    business_unit   = fields.Char('BU', readonly=True)
    company_id      = fields.Many2one('res.company','Branch', readonly=True)
    month           = fields.Integer('Month', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
                    CREATE VIEW {self._table} AS
                    SELECT
                        sol.id                                   AS id,
                        so.date_order                           AS date_order,
                        so.ticket_id                            AS ticket_id,
                        so.id                                   AS order_id,
                        pt.default_code                         AS product_code,
                        COALESCE(
                            pt.name->>'vi_VN',
                            pt.name->>'en_US'
                        )                                       AS product_name,
                        pt.uom_id                               AS product_uom,
                        SUM(sol.product_uom_qty)                AS product_uom_qty,
                        AVG(sol.price_unit)                     AS price_unit,
                        SUM(sol.price_total)                    AS price_total,
                        so.partner_id                           AS customer_id,
                        tk.saleperson_id                        AS sale_person_id,
                        pt.sap_business_unit                    AS business_unit,
                        so.company_id                           AS company_id,
                        EXTRACT(MONTH FROM so.date_order)::int  AS month
                    FROM sale_order_line sol
                    JOIN sale_order      so ON sol.order_id = so.id
                    JOIN product_product pp ON sol.product_id = pp.id
                    JOIN product_template pt ON pp.product_tmpl_id = pt.id
                    LEFT JOIN ticket_helpdesk tk ON so.ticket_id = tk.id
                    WHERE so.status = 'confirmed'
                    GROUP BY
                        sol.id,
                        so.id,
                        so.date_order,
                        so.ticket_id,
                        pt.default_code,
                        COALESCE(pt.name->>'vi_VN', pt.name->>'en_US'),
                        pt.uom_id,
                        so.partner_id,
                        tk.saleperson_id,
                        pt.sap_business_unit,
                        so.company_id
                """)
