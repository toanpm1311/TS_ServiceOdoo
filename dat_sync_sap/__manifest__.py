{
    'name': 'DAT SAP Data Synchronization',
    'summary': 'Synchronize data between Odoo and SAP system for DAT project',
    'description': """
This module provides seamless integration between Odoo and the SAP system for DAT company.
It allows automatic or manual synchronization of key business data.
Features:
- Bi-directional synchronization (SAP ↔ Odoo)
- Secure data exchange with SAP API

Developed specifically for DAT, this module ensures accurate and efficient data flow between ERP systems.
    """,
    'version': '17.0.1.0.31',
    'category': 'Integration', 
    'license': 'LGPL-3',
    'author': 'DAT Group',
    'depends': ['dat_base', 'dat_product', 'dat_helpdesk_technical_proposal', 'dat_hr_employee', 'dat_partner'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/ir_cron_views.xml',
        'views/ir_cron_history_views.xml',
        'views/product_product_views.xml',
        'views/sale_order_views.xml',
        'views/ticket_helpdesk_views.xml',
        'views/technical_proposal_views.xml',
        'wizard/sync_specific_model_wizard_views.xml',
        'data/product_variant_data.xml',
        'data/ir_cron_data.xml',
        'wizard/create_serial_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dat_sync_sap/static/src/views/stock_lot_list_controller.js',
            'dat_sync_sap/static/src/views/stock_lot_list_view.js',
            'dat_sync_sap/static/src/views/stock_lot_button.xml',
            'dat_sync_sap/static/src/css/noti.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': True,
    'sequence': 20,
}
