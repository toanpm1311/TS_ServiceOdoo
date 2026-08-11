{
    'name': 'DAT Sale',
    'summary': 'Extend Sale for DAT system',
    'description': """
This module is custommized from Odoo Sale module to adapt with DAT system.
    """,
    'version': '17.0.1.0.25',
    'category': 'Sale',
    'license': 'LGPL-3',
    'author': 'DAT Group',
    'depends': ['dat_product', 'sale_stock', 'dat_price_list'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',    
        'views/sale_portal_templates.xml',   
        'report/custom_sale_report.xml', 
        'wizard/sale_order_cancel_views.xml',
        'wizard/sale_order_reject_views.xml',
        'wizard/import_export_products_wizard_views.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 40,
}
