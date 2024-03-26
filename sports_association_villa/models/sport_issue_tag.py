from odoo import fields, models

class SportIssueTag(models.Model):
    _name = 'sport.issue.tag'
    _description = 'Sport Issue Tag'

    name = fields.Char('Name', required=True)
    color = fields.Integer(string='Color', default=0)

    issue_ids = fields.Many2many('sport.issue', 'sport_issue_tags_rel', 'tag_id', 'issue_id', string='Issue')
