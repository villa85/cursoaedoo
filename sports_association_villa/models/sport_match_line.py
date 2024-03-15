from odoo import fields, models, api, Command

class SportMatchLine(models.Model):
    _name = 'sport.match.line'
    _description = 'Sport Match Line'
    _order = 'score desc'
    _sql_constraints = [('team_unique_in_match', 'UNIQUE(sport_match_id, team_id)', 'Team must be unique in match')]

    team_id = fields.Many2one('sport.team', string='Team', required=True)
    score = fields.Integer(string='Score', required=False, default=0)
    sport_match_id = fields.Many2one('sport.match', string='Match')
