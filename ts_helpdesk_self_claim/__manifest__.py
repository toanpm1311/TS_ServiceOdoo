{
    "name": "Helpdesk Self Claim",
    "summary": "Cho phep nhan vien xem danh sach cong viec va tu tiep nhan ticket",
    "version": "17.0.1.0.0",
    "author": "DAT Group",
    "category": "Helpdesk",
    "depends": [
        "dat_website_helpdesk",
        "dat_helpdesk_steps_sla",
    ],
    "data": [
        "security/helpdesk_self_claim_security.xml",
        "views/ticket_helpdesk_views.xml",
        "views/helpdesk_menu_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
