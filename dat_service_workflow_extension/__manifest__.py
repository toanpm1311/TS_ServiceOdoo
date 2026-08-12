{
    'name': 'DAT Service Workflow Extension',
    'summary': 'Checklist, quotation defaults, warranty and service warehouse extensions',
    'description': """
Extend service helpdesk and quotation flow with work checklists, default material
proposal data, manufacturer warranty visibility, SO notes and extra service warehouses.
    """,
    'version': '17.0.1.3.2',
    'category': 'Services/Helpdesk',
    'license': 'LGPL-3',
    'author': 'DAT Group',
    'depends': [
        'dat_helpdesk_technical_proposal',
        'dat_website_helpdesk',
        'ts_helpdesk_self_claim',
        'dat_sale',
        'dat_product',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/helpdesk_rule_overrides.xml',
        'data/ir_sequence_data.xml',
        'views/ticket_helpdesk_views.xml',
        'views/create_ticket_wizard_views.xml',
        'views/technical_proposal_views.xml',
        'views/sale_order_views.xml',
        'views/stock_lot_views.xml',
        'report/sale_report_templates.xml',
        'report/service_work_checklist_report.xml',
        'report/standard_quotation_report.xml',
        'data/mail_template_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'sequence': 45,
}
