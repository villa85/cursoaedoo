from odoo import fields, models, api, Command

class SportIssueState(models.TransientModel):
    _name = "sport.issue.state"
    _description = "Set state to done"

    date = fields.Date('Date')

    def set_done(self):
        active_ids = self.env.context.get('active_ids')
        issues = self.env['sport.issue'].browse(active_ids)
        issues = issues.filtered(lambda r: r.state != 'open')
        # issues = self.env['sport.issue'].search([('id','in', active_ids),('state', '!=', 'open')])
        issues.write({'date': self.date})
        issues.action_done()
