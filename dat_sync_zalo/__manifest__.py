{
    'name': 'DAT Zalo Data Synchronization',
    'summary': 'Synchronize data from Zalo to DAT TechService',
    'description': """
This module provides seamless integration between Zalo and the DAT TechService for DAT company.
It allows automatic or manual synchronization of key business data.
    """,
    'version': '17.0.1.0.1',
    'category': 'Integration', 
    'license': 'LGPL-3',
    'author': 'DAT Group',
    'depends': ['dat_website_helpdesk', 'dat_sync_sap'],
    'data': [
        'data/res_config_settings_data.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 20,
}
