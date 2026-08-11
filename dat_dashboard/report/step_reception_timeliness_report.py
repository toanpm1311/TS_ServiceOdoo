# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class StepReceptionTimelinessReport(models.Model):
    _name = 'step.reception.timeliness.report'
    _description = 'Step Reception Timeliness Report'
    _auto = False

    ticket_id = fields.Many2one('ticket.helpdesk', 'Ticket', readonly=True)
    create_date = fields.Datetime(string='Create Date', readonly=True)
    department_id = fields.Many2one('hr.department', string='Department', readonly=True)
    company_id = fields.Many2one('res.company', string='Branch', readonly=True)
    status = fields.Selection([
        ('on time', 'On Time'),
        ('over time', 'Over Time'),
        ('other', 'Other')],
        string='Status', readonly=True)

    @api.model
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        cr = self.env.cr

        step_ids = [
            self.env.ref('dat_website_helpdesk.step_wf1_receiving_and_inspection').id,
            self.env.ref('dat_website_helpdesk.step_wf2_receiving_and_inspection').id,
            self.env.ref('dat_website_helpdesk.step_wf3_receiving_and_inspection').id,
            self.env.ref('dat_website_helpdesk.step_wf4_receiving_and_inspection').id,
        ]
        step_ids_str = ','.join(map(str, step_ids))

        cr.execute(f"""
                    CREATE VIEW {self._table} AS
                    WITH latest_status AS (
                        SELECT
                            ticket_id,
                            MAX(create_date) AS max_date
                        FROM ticket_step_status
                        WHERE step_id IN ({step_ids_str})
                        GROUP BY ticket_id
                    )
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY t.create_date, t.department_id, t.branch) AS id,
                        ls.ticket_id,
                        t.create_date        AS create_date,
                        t.department_id,
                        t.branch           AS company_id,
                        CASE
                            WHEN sts.time_spent IS NULL         THEN 'other'
                            WHEN sts.time_spent <= sts.time_sla THEN 'on time'
                            ELSE 'over time'
                        END AS status
                    FROM latest_status ls
                    JOIN ticket_step_status sts
                      ON sts.ticket_id = ls.ticket_id
                     AND sts.create_date = ls.max_date
                    JOIN ticket_helpdesk t
                      ON t.id = ls.ticket_id
                     AND t.active = TRUE
                """)
