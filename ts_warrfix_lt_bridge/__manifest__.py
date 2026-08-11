{
    'name': 'TS Warranty Fix LT Bridge',
    'version': '17.0.3.2.5',
    'summary': 'Bridge LT stock display and split SAP SO/DXVT creation between main/LT warehouses',
    'category': 'Sales',
    'author': 'OpenAI',
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'dat_website_helpdesk',
    ],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
