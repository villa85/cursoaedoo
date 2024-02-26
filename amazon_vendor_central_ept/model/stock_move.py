from odoo import models, fields, api, _

class stock_move(models.Model):
    _inherit = "stock.move"

    
    def btn_action_cancel(self):
        return self.action_cancel()