from odoo import fields, models, api, Command

class SportCreateIssueWizard(models.TransientModel):
    _name = "sport.create.issue.wizard"
    _description = "Sport Create Issue Wizard"

    def _get_default_clinic(self):
        model = self.env.context.get('active_model')
        if model == 'sport.clinic':
            return self.env.context.get('active_id', False)
        else:
            return False

    def _get_default_player(self):
        model = self.env.context.get('active_model')
        if model == 'sport.player':
            return self.env.context.get('active_id', False)
        else:
            return False

    name = fields.Char('Name', required=True)
    player_id = fields.Many2one('sport.player', string='Player', default=_get_default_player) #  al final la funcion no se ejecuta, pq he agregado en en vista por contexto el valor de active_id (id del jugador seleccionado)
    clinic_id = fields.Many2one('sport.clinic', string='Clinic', default=_get_default_clinic) #  al final la funcion no se ejecuta, pq he agregado en en vista por contexto el valor de active_id (id de la clinica seleccionada)
    # player_id = fields.Many2one('sport.player', string='Player', default = lambda self: self.env.context.get('active_id', False))
    # clinic_id = fields.Many2one('sport.clinic', string='Clinic', default = lambda self: self.env.context.get('active_id', False))

    def create_issue(self):
        # import wdb; wdb.set_trace()
        # active_id = self.env.context.get('active_id')                  OTRA MANERA DE OBTENER EL ID IGUAL DE VALIDA
        # if self.env.context.get('active_model') == 'sport.clinic':
        #     clinic = self.env['sport.clinic'].browse(active_id)
        #     self.clinic_id = clinic.id
        # if self.env.context.get('active_model') == 'sport.player':
        #     player = self.env['sport.player'].browse(active_id)
        #     self.player_id = player.id
        vals = {
            'name': self.name,
            'clinic_id': self.clinic_id.id,
            'player_id': self.player_id.id}
        issue = self.env['sport.issue'].create(vals)


        return {
            'name': 'Issue created',
            'type': 'ir.actions.act_window',
            'res_model': 'sport.issue',
            'view_mode': 'form',
            'res_id': issue.id,
            'target': 'current'
            }