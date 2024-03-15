from odoo import fields, models, api, Command
from odoo.exceptions import ValidationError


class SportIssue(models.Model):
    _name = 'sport.issue'
    _description = 'Sport Issue'

    name = fields.Char('Name', required=True)
    description = fields.Text('Description')
    date = fields.Date('Date', default=fields.Date.today())
    assistance = fields.Boolean(string='Assistance', help='Check if the issue has assistance')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('done', 'Done')],
        string = 'State',
        default='draft')
    player_id = fields.Many2one('sport.player', string='Player')
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.context.get('user_id', self.env.user.id)) # User responsible for the issue, by default the creator of the issue
    sequense = fields.Integer(string = 'Sequense', default=10)
    solution = fields.Html('Solution')
    clinic_id = fields.Many2one('sport.clinic', string='Clinic')
    tag_ids = fields.Many2many('sport.issue.tag', string='Tags')
    sport_action_to_do_ids = fields.One2many('sport.action.to.do', 'sport_issue_id', string='Actions to do')
    color = fields.Integer(string ='Color', default=0)
    cost = fields.Float('Cost')
    assigned = fields.Boolean('Assigned', compute='_compute_assigned', inverse='_inverse_assigned', search = '_search_assigned', store=True)
    # user_phone = fields.Char('Phone', related='user_id.partner_id.phone', readonly=True)
    user_phone = fields.Char('Phone', readonly=True)

    _sql_constraints = [
                ('name_unique', 'unique(name)', 'The name of the issue must be unique.'),
            ]
    @api.onchange('user_id')
    def _onchange_user_phone(self):
        for record in self:
            record.user_phone = record.user_id.partner_id.phone

    @api.onchange('clinic_id')
    def _onchange_clinic(self):
        for record in self:
            if record.clinic_id:
                record.assistance = True
            else:
                record.assistance = False

    @api.constrains('cost')
    def _check_cost(self):
        for record in self:
            if record.cost < 0:
                raise ValidationError('The cost must be positive')


    @api.depends('user_id')
    def _compute_assigned(self):
        for record in self:
            record.assigned = bool(record.user_id)

    def _inverse_assigned(self):
        for record in self:
            if not record.assigned:
                record.user_id = False
            else:
                record.user_id = record.env.user

    def _search_assigned(self, operator, value):
        if operator == '=':
            return [('user_id', operator, bool(value))]
        else:
            return []

    def action_open(self):
        for record in self:
            record.state = 'open'

    def action_draft(self):
        for record in self:
            record.state = 'draft'

    def action_done(self):
        for record in self:
            record.state = 'done'

    def action_add_tag(self):
        for record in self:
            # import wdb; wdb.set_trace()
            # import pdb; pdb.set_trace()
            tag_ids = self.env['sport.issue.tag'].search([('name', 'ilike', 'record.name')])
            if tag_ids:
                # before_tag_ids = record.tag_ids
                # final_tag_ids |= before_tag_ids + tag_ids
                record.tag_ids = [Command.set(tag_ids.ids)]
                # record.tag_ids = [(6, 0 tag_ids.ids)]
            else:
                record.tag_ids = [Command.create({'name': record.name})]
                # record.tag_ids = [0, 0, ({'name': record.name})]

    def _cron_remove_unused_tags(self):
        tag_ids = self.env['sport.issue.tag'].search([])
        for tag in tag_ids:
            issue = self.env['sport.issue'].search([('tag_ids', 'in', tag.id)])
            if not issue:
                tag.unlink()
