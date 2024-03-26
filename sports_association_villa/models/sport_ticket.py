from odoo import fields, models, api, Command

class SportTicket(models.Model):
    _name = 'sport.ticket'
    _description = 'Sport Ticket'

    name = fields.Char('Name', required=True)
    customer_id = fields.Many2one('res.partner', string='Customer')
    match_id = fields.Many2one('sport.match', string='Match')

    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('sport.ticket')
        res = super().create(vals)
        return res