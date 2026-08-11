{
    'name': 'DAT Employee',
    'summary': 'Extend Employee for DAT system',
    'description': """
This module is custommized from Odoo Employee module to adapt with DAT system.
    """,
    'version': '17.0.1.0.2',
    'category': 'Product',
    'license': 'LGPL-3',
    'author': 'DAT Group',
    'depends': ['dat_base'],
    'data': [
        'views/hr_employee_views.xml',
        'views/hr_department_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 30,
}
