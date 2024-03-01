from odoo import fields, models

class SportIssue(models.Model):
    _name = 'sport.issue'
    _description = 'Sport Issue'

    name = fields.Char('Name', required=True)
    description = fields.Text('Description')
    date = fields.Date('Date')
    assistance = fields.Boolean(string='Assistance', help='Check if the issue has assistance')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('done', 'Done')], 
        string = 'State',
        default='draft')