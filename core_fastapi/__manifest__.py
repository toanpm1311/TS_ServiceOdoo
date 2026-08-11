{
    'name': 'Core FastAPI',
    'version': '17.0.0.0.12',
    'summary': 'Core API to authenticate and manage users in odoo',
    'description': """
    This module based on fastapi module. It provides apis to login, logout, change password, register, reset and get info users 
    """,
    'license': 'LGPL-3',
    'data': [
        'data/fastapi_endpoint_data.xml',
        'data/auth_oauth_data.xml',
        'views/res_config_settings_views.xml',
        'views/core_fastapi_menus.xml',
    ],
    'depends': ['auth_oauth', 'fastapi', 'auth_signup'],
    'installable': True,
    'application': True,
    'auto_install': True,
}
