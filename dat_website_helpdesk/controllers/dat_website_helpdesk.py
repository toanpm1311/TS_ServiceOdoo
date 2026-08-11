import datetime as DT
from odoo import http
from odoo.http import request


class HelpDeskDashboard(http.Controller):
    """Controller for handling Help Desk dashboard requests."""

    @http.route(['/helpdesk_dashboard'], type='json', auth="public")
    def helpdesk_dashboard(self):
        """Retrieves statistics for tickets in different steps.
        Returns:dict: Dashboard statistics including counts and IDs for each
        step.
        """
        step_names = ['Inbox', 'Draft', 'In Progress', 'Canceled', 'Done',
                       'Closed']
        step_ids = {
            name: request.env['ticket.step'].search([('name', '=', name)],
                                                     limit=1).id for name in
            step_names}
        new_steps = [step_ids['Inbox'], step_ids['Draft']]

        def get_ticket_data(step_ids):
            tickets = request.env["ticket.helpdesk"].search(
                [('step_id', 'in', step_ids)])
            return len(tickets), [ticket.id for ticket in tickets]
        dashboard_values = {
            'new': (get_ticket_data(new_steps))[0],
            'new_id': (get_ticket_data(new_steps))[1],
            'in_progress': (get_ticket_data([step_ids['In Progress']]))[0],
            'in_progress_id': (get_ticket_data([step_ids['In Progress']]))[1],
            'canceled': (get_ticket_data([step_ids['Canceled']]))[0],
            'canceled_id': (get_ticket_data([step_ids['Canceled']]))[1],
            'done': (get_ticket_data([step_ids['Done']]))[0],
            'done_id': (get_ticket_data([step_ids['Done']]))[1],
            'closed': (get_ticket_data([step_ids['Closed']]))[0],
            'closed_id': (get_ticket_data([step_ids['Closed']]))[1]}
        return dashboard_values

    def helpdesk_dashboard_week(self):
        """ Retrieves statistics for tickets created in the past week.
        Returns:
        dict: Dashboard statistics including counts and IDs for each step."""
        today = DT.date.today()
        week_ago = str(today - DT.timedelta(days=7)) + ' '
        step_names = ['Inbox', 'Draft', 'In Progress', 'Canceled', 'Done',
                       'Closed']
        steps = {
            name: request.env['ticket.step'].search([('name', '=', name)],
                                                     limit=1).id for name in
            step_names}
        step_ids = [steps['Inbox'], steps['Draft']]
        def get_ticket_data(step_id):
            count = request.env["ticket.helpdesk"].search_count(
                [('step_id', '=', step_id), ('create_date', '>', week_ago)])
            ids = request.env["ticket.helpdesk"].search(
                [('step_id', '=', step_id),
                 ('create_date', '>', week_ago)]).ids
            return count, ids
        new_count, new_ids = get_ticket_data(step_ids)
        in_progress_count, in_progress_ids = get_ticket_data(
            steps['In Progress'])
        canceled_count, canceled_ids = get_ticket_data(steps['Canceled'])
        done_count, done_ids = get_ticket_data(steps['Done'])
        closed_count, closed_ids = get_ticket_data(steps['Closed'])
        dashboard_values = {
            'new': new_count,
            'in_progress': in_progress_count,
            'canceled': canceled_count,
            'done': done_count,
            'closed': closed_count,
            'new_id': new_ids,
            'in_progress_id': in_progress_ids,
            'canceled_id': canceled_ids,
            'done_id': done_ids,
            'closed_id': closed_ids,
        }
        return dashboard_values

    @http.route(['/helpdesk_dashboard_month'], type='json', auth="public")
    def helpdesk_dashboard_month(self):
        """Retrieves statistics for tickets created in the past month.
        Returns:
          dict: Dashboard statistics including counts and IDs for each step."""
        today = DT.date.today()
        month_ago = today - DT.timedelta(days=30)
        week_ago = str(month_ago) + ' '
        steps = request.env['ticket.step'].search([('name', 'in',
                                                      ['Inbox', 'Draft',
                                                       'In Progress',
                                                       'Canceled', 'Done',
                                                       'Closed'])])
        step_ids = {step.name: step.id for step in steps}
        def get_step_data(step_names):
            step_ids_list = [step_ids[name] for name in step_names]
            tickets = request.env["ticket.helpdesk"].search(
                [('step_id', 'in', step_ids_list),
                 ('create_date', '>', week_ago)])
            return len(tickets), [ticket.id for ticket in tickets]
        new_count, new_ids = get_step_data(['Inbox', 'Draft'])
        in_progress_count, in_progress_ids = get_step_data(['In Progress'])
        canceled_count, canceled_ids = get_step_data(['Canceled'])
        done_count, done_ids = get_step_data(['Done'])
        closed_count, closed_ids = get_step_data(['Closed'])
        dashboard_values = {
            'new': new_count,
            'in_progress': in_progress_count,
            'canceled': canceled_count,
            'done': done_count,
            'closed': closed_count,
            'new_id': new_ids,
            'in_progress_id': in_progress_ids,
            'canceled_id': canceled_ids,
            'done_id': done_ids,
            'closed_id': closed_ids,
        }
        return dashboard_values

    @http.route(['/helpdesk_dashboard_year'], type='json', auth="public")
    def helpdesk_dashboard_year(self):
        """Retrieves statistics for tickets created in the past year.
        Returns:
            dict: Dashboard statistics including counts and IDs for each step.
        """
        today = DT.date.today()
        year_ago = today - DT.timedelta(days=360)
        steps = ['Inbox', 'Draft', 'In Progress', 'Canceled', 'Done', 'Closed']
        step_ids = {
            step: request.env['ticket.step'].search([('name', '=', step)],
                                                      limit=1).id for step in
            steps}
        def get_ticket_data(step_name):
            step_id = step_ids[step_name]
            tickets = request.env["ticket.helpdesk"].search(
                [('step_id', '=', step_id), ('create_date', '>', year_ago)])
            return len(tickets), [ticket.id for ticket in tickets]
        dashboard_values = {}
        for step in steps:
            count, ids = get_ticket_data(step)
            dashboard_values[step.lower()] = count
            dashboard_values[f'{step.lower()}_id'] = ids
        return dashboard_values
