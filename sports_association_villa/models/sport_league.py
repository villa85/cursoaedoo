from odoo import fields, models, api, Command

class SportLeague(models.Model):
    _name = 'sport.league'
    _description = 'Sport League'

    name = fields.Char(string='Name', required=True)
    begin_date = fields.Date(string='Begin Date', required=False)
    end_date = fields.Date(string='End Date', required=False)
    sport_id = fields.Many2one('sport.sport', string='Sport')
    sport_league_ids = fields.One2many('sport.league.line', 'sport_league_id', string='Leagues Lines')
    match_ids = fields.One2many('sport.match', 'league_id', string='Matches')
    match_count = fields.Integer(string='Match Count', compute='_compute_match_count')
    # _sql_constraints = [
    #     ('date_check', 'CHECK(begin_date > end_date)', 'Begin date must be less than or equal to end date!')
    # ]


    def _compute_match_count(self):
        for record in self:
            record.match_count = len(record.match_ids)

    def action_view_matches(self):
        return {
            'name': 'Matches',
            'type': 'ir.actions.act_window',
            'res_model': 'sport.match',
            'view_mode': 'tree,form',
            'domain': [('league_id', '=', self.id)],
        }

    @api.constrains('begin_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.begin_date > record.end_date:
                raise models.ValidationError('Begin date must be less than or equal to end date!')

    def set_score(self):
        for record in self.sport_league_ids:
            team = record.team_id
            score_points = self.env['sport.match'].search([('sport_id', '=', self.sport_id.id), ('winner_id', '=', team.id)]).mapped('score_winner')
            record.points = sum(score_points)

    def _cron_set_score(self):
        leagues = self.env['sport.league'].search([])
        leagues.set_score()