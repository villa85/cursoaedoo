from odoo import fields, models

class SportPlayer(models.Model):
    _name = 'sport.player'
    _description = 'Sport Player'

    name = fields.Char('Name', required=True)
    age = fields.Integer('Age')
    position = fields.Char('Position')
    team_id = fields.Many2one('sport.team', string='Team')
    starting_layer = fields.Boolean(string='Starting Player')