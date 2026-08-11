{
    'name': 'DAT Base',
    'summary': 'Base information for DAT project',
    'description': """
- This module defines base information for DAT company's system.
- This module hides any menu items that are not in the whitelist for the current user.
    """,
    'version': '17.0.1.0.30',
    'license': 'LGPL-3',
    'author': 'DAT Group',
    'depends': ['dat_website_helpdesk', 'web', 'stock', 'product', 'hr_holidays'],
    'data': [
        'data/group_settings.xml',
        'report/helpdesk_ticket_report_template.xml',
        'views/menus.xml',
        'views/custom_product_action_view.xml',
        'views/custom_res_partner_view_form.xml',
        'views/hr_employee_views.xml',
        'views/res_partner_views.xml',
        'data/resource_data.xml',
        'data/resource_calendar_data.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "dat_base/static/src/js/company_service.js",
            "dat_base/static/src/js/window_title_customize.js",
            "dat_base/static/src/js/web_chatter_position.js",
            "dat_base/static/src/**/*.scss",
        ],
    },
    'installable': True,
    'application': True,
    'post_init_hook': '_dat_base_post_init',
    'auto_install': True,
    'sequence': 10,
}
