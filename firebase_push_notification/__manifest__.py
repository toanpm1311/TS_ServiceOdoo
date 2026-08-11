{
    'name': 'Firebase Push Notification',
    'version': '17.0.1.0.1',
    'category': 'Mail',
    'summary': 'Mail',
    'description': """
        Provide free unlimited push notifications on android phones, absolutely free,
        which free android App (used Firebase Push Notifications)
        """,
    'depends': ['base','web','mail', 'account'],
    'data': [
        'security/mobile_app_security.xml',
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/mobile_app_push_notification_views.xml',
        'views/push_notification_log_partner_views.xml',
        'wizards/res_partner_firebase_message_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
