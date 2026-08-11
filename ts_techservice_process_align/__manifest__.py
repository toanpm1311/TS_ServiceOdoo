{
    "name": "TS Techservice Process Align",
    "summary": "Align warranty, remote support and 1-1 exchange workflow with DAT process",
    "version": "17.0.1.0.0",
    "category": "Services/Helpdesk",
    "author": "OpenAI / DAT prototype",
    "license": "LGPL-3",
    "depends": [
        "dat_website_helpdesk",
        "ts_techservice_flow_guard",
        "mail",
    ],
    "data": [
        "security/ir_rule_overrides.xml",
        "views/sale_order_views.xml",
        "views/ticket_helpdesk_views.xml",
    ],
    "installable": True,
    "application": False,
}
