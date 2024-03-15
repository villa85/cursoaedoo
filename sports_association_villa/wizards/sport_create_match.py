from odoo import fields, models, api, Command

class SportCreateMatch(models.TransientModel):
    _name = "sport.create.match"
    _description = "Sport Create Match"

    league_id = fields.Many2one('sport.league', string='League')
    sport_id = fields.Many2one('sport.sport', string='Sport', related='league_id.sport_id', store=True)
    team_ids = fields.Many2many('sport.team', string='Teams')
    start_date = fields.Datetime(string='Date')
    allowed_team_ids = fields.Many2many('sport.team', relation='sport_match_team_rel', string= "Allowed Teams", compute='_compute_allowed_team_ids', store=True)

    @api.depends('league_id')
    def _compute_allowed_team_ids(self):
        for rec in self:
            rec.allowed_team_ids = self.league_id.sport_league_ids.team_id.ids

    def create_match(self):
        vals = {
            'league_id': self.league_id.id,
            'sport_id': self.sport_id.id,
            'start_date': self.start_date,
            'sport_match_line_ids': [(0, 0, {'team_id': team.id}) for team in self.team_ids]}
        match = self.env['sport.match'].create(vals)
        return {
            'name': 'Match',
            'type': 'ir.actions.act_window',
            'res_model': 'sport.match',
            'view_mode': 'form',
            'res_id': match.id,
            'target': 'current'
            }