from odoo import fields, models, api
from datetime import datetime



class SportPlayer(models.Model):
    _name = 'sport.player'
    _description = 'Sport Player'
    _inherits = {'res.partner': 'partner_id'}

    name = fields.Char(related='partner_id.name', inherited=True, readonly=False)
    partner_id = fields.Many2one('res.partner', string='Partner', required=True, ondelete='cascade')
    birtday = fields.Date(string ='Birthday', copy=False)
    age = fields.Integer(string = 'Age', compute='_compute_age', store=True, copy=False)
    position = fields.Char('Position', copy=False)
    team_id = fields.Many2one('sport.team', string='Team')
    starting_player = fields.Boolean(string='Starting Player', default=True, copy=False)
    sport = fields.Char('Sport', related='team_id.sport_id.name', store=True)
    color = fields.Integer(string ='Color', default=0, copy=False)
    active = fields.Boolean('Active', default=True)

    @api.depends('birtday')
    def _compute_age(self):
        # import pdb; pdb.set_trace()
        for record in self:
            if record.birtday:
                record.age = (fields.Date.today() - record.birtday).days // 365
                # wdb.set_trace()
            else:
                record.age = 0