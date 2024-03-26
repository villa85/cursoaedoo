from odoo import fields, models, api, Command

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_sport_ticket = fields.Boolean(string='Is Sport Ticket')