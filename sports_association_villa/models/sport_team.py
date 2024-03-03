from odoo import fields, models

class SportTeam(models.Model):
    _name = 'sport.team'
    _description = 'Sport Team'

    name = fields.Char('Name', required=True)
    logo = fields.Binary("Logo")
    # logo = fields.Image("Logo", max_width=1920, max_height=1920)
    players_ids = fields.One2many('sport.player', 'team_id', string='Players')
    sport_id = fields.Many2one('sport.sport', string='Sport')