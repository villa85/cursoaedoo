{
    'name': 'Sports Association Sale',
    'summary': 'Manage sport associations and sales',
    'version': '17.0.1.0.0',
    'category': 'Sports',
    'author': 'Yuniel Villalón',
    'license': 'AGPL-3',
    'application': False,
    'installable': True,
    'depends': ['sports_association_villa','sale_management','crm'],
    'data': [
            'views/sport_ticket_views.xml',
            'views/sale_order_views.xml',
            'views/product_template_views.xml',
],
}
