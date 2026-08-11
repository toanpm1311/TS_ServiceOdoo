{
    'name': 'DAT SAP Configuration',
    'summary': 'Manages SAP connection settings like API and authentication.',
    'description': """
This module manages the configuration settings required to connect Odoo with an external SAP system,
including API endpoints and authentication details.
    """,
    'version': '17.0.1.0.3',
    'category': 'Integration',
    'license': 'LGPL-3',
    'author': 'DAT Group',
    'depends': [],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
    'sequence': 20,
}
