from odoo import fields, models, api, Command
from odoo.exceptions import ValidationError
import re

class WebsiteVisitor(models.Model):
    _inherit = 'website.visitor'

    email = fields.Char(string="Email", required=True)

    how_you_found_us = fields.Selection([
                    ('third_parties', 'Third Parties/Networks'),
                    ('social_search', 'Social Media/Internet Search')],
                    string = 'How you found us',
                    default='third_parties')

    @api.constrains('email')
    def _check_email_format(self):
        """Valida el formato del correo electrónico."""
        for visitor in self:
            if visitor.email:
                if not self._is_valid_email(visitor.email):
                    raise ValidationError("The e-mail format is not valid..")

    def _is_valid_email(self, email):
        """Valida el formato del correo electrónico."""
        return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))