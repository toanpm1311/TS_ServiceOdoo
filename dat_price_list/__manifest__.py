{
    'name': 'DAT Price List',
    'summary': 'Manage simple item code price list',
    'description': """
Manage editable item code prices and import them from Excel.
    """,
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'license': 'LGPL-3',
    'author': 'DAT Group',
    'depends': ['dat_base'],
    'data': [
        'security/ir.model.access.csv',
        'views/dat_price_list_item_views.xml',
        'wizard/dat_price_list_import_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 45,
}
