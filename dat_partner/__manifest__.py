{
    'name': 'DAT Partner (Customer/Vendor)',
    'summary': 'Manage accounts for DAT system',
    'description': """
This module is custommized from Odoo Partner module to adapt with DAT system.
    """,
    'version': '17.0.1.0.5',
    'category': 'Integration',
    'license': 'LGPL-3',
    'author': 'DAT Group',
    'depends': ['dat_base', 'dat_hr_employee'],
    'data': [
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 30,
}
