from odoo import fields, models, api, Command
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sport_ticket_ids = fields.One2many('sport.ticket', 'sale_order_id', string='Sport Tickets')

    def action_cancel(self):
        res = super().action_cancel()
        self.sport_ticket_ids.unlink()
        return res

    def create_sport_ticket(self):
        vals = {
            'name': self.name,
            'customer_id': self.partner_id.id,
            'sale_order_id': self.id,
        }
        self.env['sport.ticket'].create(vals)

#? 2. NO PERMITIR PEDIDOS DE VENTA CON CANTIDADES CERO

    def action_confirm(self):
        for order in self:
            if order.order_line.product_uom_qty == 0:
                raise ValidationError('The quantity of products cannot be zero')
            res = super().action_confirm()
        return res

    def delete_sales_with_zero_quantity(self):
        for order in self:
            zero_quantity_lines = order.order_line.filtered(lambda line: line.product_uom_qty == 0)
            zero_quantity_lines.unlink()

#?#######################################################################################

#! This method is called when the user confirms the sale order and creates the sport tickets
    # def action_confirm(self):
    #     res = super().action_confirm()
    #     for order in self:
    #         if order.order_line.product_id.is_sport_ticket:
    #             order.create_sport_ticket()
    #     return res