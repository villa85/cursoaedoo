from odoo import models, fields, api, _

class Stock_Quant_Package(models.Model):
    _name = 'stock.quant.package'
    _inherit = ['stock.quant.package', 'delivery.carrier']


    # package_route_ids = fields.Many2many('delivery.carrier', 'stock_quant_package_route_rel', 'package_id', 'carrier_id', 'Routes')
    shipping_selectable = fields.Boolean("Applicable on Shipping Methods")
    # route_ids = fields.Many2many('stock.route', 'stock_route_shipping', 'shipping_id', 'route_id', 'Routes', domain=[('shipping_selectable', '=', True)])
    route_ids = fields.Many2many('delivery.carrier', 'stock_quant_package_route_rel', 'package_id', 'carrier_id', 'Routes', domain=[('shipping_selectable', '=', True)])
    country_ids = fields.Many2many('res.country', 'stock_quant_package_country_rel', 'package_id', 'country_id', 'Countries')
    state_ids = fields.Many2many('res.country.state', 'stock_quant_package_state_rel', 'package_id', 'state_id', 'States')
    zip_prefix_ids = fields.Many2many('delivery.zip.prefix', 'stock_quant_package_prefix_rel', 'package_id', 'zip_prefix_id', 'Zip Prefixes',)

    def _compute_fixed_price(self):
        pass
    def _compute_supports_shipping_insurance(self):
        pass
    def _set_product_fixed_price(self):
        pass
#----------------------------------------------------------
    def _compute_current_picking_info(self):
        """ When a package is in displayed in picking, it gets the picking id trough the context, and this function
        populates the different fields used when we move entire packages in pickings.
        """
        for package in self:
            picking_id = self.env.context.get('picking_id')
            if not picking_id:
                package.current_picking_move_line_ids = False
                continue
            package.current_picking_move_line_ids = package.move_line_ids.filtered(lambda ml: ml.picking_id.id == picking_id)

    handling_instructions =fields.Selection([('BIG','Oversized'),('CRU','Fragile'),('EAT','Food'),('HWC','Handle with Care')], string = 'Handling Instructions')
    amazon_carrier_code = fields.Char("Amazon Carrier Reference")
    amazon_package_weight = fields.Float("Amazon Package Weight")
    package_type = fields.Selection([('pallet','Pallet'),('carton','Carton')])
    stock_pack_operation_ids_ept = fields.One2many('stock.pack.operation',string="Stock Pack Operation",compute="_compute_current_picking_info")
    # move_line_ids = fields.One2many('stock.pack.operation', 'package_id')
