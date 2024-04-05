from odoo import fields, models, api, Command
from odoo.exceptions import ValidationError

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    how_you_found_us = fields.Selection([
                        ('third_parties', 'Third Parties/Networks'),
                        ('social_search', 'Social Media/Internet Search')],
                        string = 'How you found us',
                        default='third_parties',
                        tracking=True)