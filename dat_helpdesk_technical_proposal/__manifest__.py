{
    'name': 'DAT Technical Proposal',
    'summary': 'DAT system technical ',
    'description': """
This module is custommized from Odoo product module to manage technical proposals.
    """,
    'version': '17.0.1.0.20',
    'category': 'Technical Proposal',
    'license': 'LGPL-3',
    'author': 'DAT Group',
    'depends': ['dat_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_portal_template.xml',
        'views/technical_proposal_views.xml',
        'views/technical_proposal_template_views.xml',
        'views/ticket_helpdesk_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 30,
}
