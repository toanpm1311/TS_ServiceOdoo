# -*- coding: utf-8 -*-
{
    'name': 'DAT TechService Notification Management',
    'version': '17.0.1.2.4',
    'summary': 'Manages The Push Notifications And The In-app Notifications',
    'author': "DAT Group",
    'company': 'DAT Group',
    'description': """
    This module extends the firebase_push_notification module and adds the apis to implement the notifications in the system.
    Include:
        - Manages the push notifications
        - Manages the in-app notifications
    """,
    'license': 'LGPL-3',
    'depends': ['core_fastapi', 'firebase_push_notification'],
    'data': [
        'data/notification_type_data.xml',
        'views/notification_template_views.xml',
        'views/res_users_notification_views.xml',
        'views/notification_type_views.xml',
        'views/dat_notification_management_menus.xml',
        'views/res_users_views.xml',
        'security/res_users_notification_security.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': True,
}
