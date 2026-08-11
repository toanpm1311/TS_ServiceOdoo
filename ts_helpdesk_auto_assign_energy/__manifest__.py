# -*- coding: utf-8 -*-
{
    "name": "Helpdesk Auto-Assign (Energy)",
    "summary": "Tự động phân công phiếu helpdesk cho mảng Năng lượng",
    "version": "17.0.1.0.0",
    "author": "DAT Group",
    # Dùng module helpdesk custom của anh, KHÔNG dùng 'helpdesk' chuẩn
    "depends": ["dat_website_helpdesk", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/auto_assign_rule_view.xml",
        "views/res_config_settings_views.xml",
    ],
    

    "installable": True,
    "category": "Helpdesk",
    "application": True,
    "license": "LGPL-3",
}
