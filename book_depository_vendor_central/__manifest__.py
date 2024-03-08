# -*- coding: utf-8 -*-
{
    'name': "Book depository vendor central",

    'summary': """
        """,

    'description': """
        Inclusión de las caracteristicas de book depository al módulo de vendor central.
    """,

    'author': "Quadit",
    'website': "https://www.quadit.io",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Desarrollo',
    'license': 'OPL-1',
    'version': '17.0',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'amazon_vendor_central_ept',
    ],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/vendor_config.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}