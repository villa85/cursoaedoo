from odoo import models,api,fields

class product_packaging(models.Model):
    _inherit="product.packaging"
    
    height = fields.Float("Height")
    width = fields.Float("Width")
    length = fields.Float("Length")
    