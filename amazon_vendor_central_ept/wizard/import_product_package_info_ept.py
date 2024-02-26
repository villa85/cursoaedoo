from odoo import models,api,fields
from odoo.exceptions import ValidationError,UserError
from io import StringIO
import base64
import csv
from datetime import datetime
from odoo.tools.float_utils import float_round, float_compare
import time
class import_product_package_info(models.TransientModel):
    _name = 'import.product.package.info.ept'
    
    choose_file = fields.Binary('Choose File',filters='*.csv')
    file_name = fields.Char("File Name")
    picking_id = fields.Many2one('stock.picking',string="Picking")
    delimiter=fields.Selection([('semicolon','Semicolon')],string="Seperator",default="semicolon")
    
    
    @api.model
    def default_get(self,fields):
        context = dict(self._context or {})
        vals =  super(import_product_package_info,self).default_get(fields)
        picking_id = context.get('active_id', [])
        vals['picking_id'] = picking_id
        return vals
    
    
    def get_file_name(self, name=datetime.strftime(datetime.now(),'%Y%m%d%H%M%S%f')):
        return '/tmp/product_package_%s_%s' %(self.env.uid,name)
    
    
    def read_file(self,file_name,file):
        imp_file = StringIO(base64.decodestring(file).decode('utf-8'))
        new_file_name = self.get_file_name(name=file_name)[0]
        file_write = open(new_file_name,'w')
        file_write.writelines(imp_file.getvalue())
        file_write.close()
        file_read = open(new_file_name, "rU")
        dialect = csv.Sniffer().sniff(file_read.readline())
        file_read.seek(0)
        if self.delimiter=='semicolon':
            reader = csv.DictReader(file_read,dialect=dialect,delimiter=';',quoting=csv.QUOTE_NONE)
        elif self.delimiter=='colon':
            reader = csv.DictReader(file_read,dialect=dialect,delimiter=',',quoting=csv.QUOTE_NONE)
        else:
            reader = csv.DictReader(file_read,dialect=dialect,delimiter='\t',quoting=csv.QUOTE_NONE)
        return reader
    
    
    def validate_fields(self, fieldname):
        '''
            This import pattern requires few fields default, so check it first whether it's there or not.
        '''
        require_fields = ['default_code', 'quantity', 'package_ref','height','width','length','weight','package_type']
        missing = []
        for field in require_fields:
            if field not in fieldname:
                missing.append(field)
             
        if len(missing) > 0:
            raise UserError(('Incorrect format found..!'), ('Please provide all the required fields in file, missing fields => %s.' %(missing)))
         
        return True
    
    def fill_dictionary_from_file(self,reader):
        product_data = []
        for row in reader:
            vals = {
                    'default_code' : row.get('default_code'),
                    'quantity' : row.get('quantity'),
                    'package_ref' : row.get('package_ref'),
                    'height' : row.get('height'),
                    'width' : row.get('width'),
                    'length' : row.get('length'),
                    'weight' : row.get('weight'),
                    'package_type' : row.get('package_type')
                }
            product_data.append(vals)
        
        return product_data
    
    
    def import_package_info(self):
        if self.file_name and self.file_name[-3:] != 'csv':
            raise Warning("You can only import CSV file")
        product_packaging_obj = self.env['product.packaging']
        product_product_obj = self.env['product.product']
        stock_move_obj = self.env['stock.move']
        stock_pack_operation = self.env['stock.pack.operation']
        stock_quant_package_obj = self.env['stock.quant.package']
        pack_op_ids =[]
        reader = self.read_file(self.file_name,self.choose_file)[0]
        fieldname = reader.fieldnames
        picking_id = self.picking_id
        if self.validate_fields(fieldname) :
            picking_id.pack_operation_product_ids.unlink()
            product_data = self.fill_dictionary_from_file(reader)
            for data in product_data:
                default_code = data.get('default_code')
                file_qty = data.get('quantity')
                package_ref = data.get('package_ref')
                height = data.get('height')
                width = data.get('width')
                length = data.get('length')
                weight = data.get('weight')
                package_type = data.get('package_type','')
                if package_type == ('pallet' or 'Pallet') :
                    package_type = 'pallet'
                if package_type == ('carton' or 'Carton') :
                    package_type = 'carton'
                product_package = product_packaging_obj.search([('height','=',float(height)),('width','=',float(width)),('length','=',float(length))])
                if not product_package:
                    product_package = product_packaging_obj.create({
                                                    'name' : 'BOX %s x %s x %s'%(height,width,length),
                                                    'height' : float(height) ,
                                                    'width' : float(width),
                                                    'length' : float(length)
                                                    })
                
                
                package = False
                if not package:
                    package = stock_quant_package_obj.search([('amazon_carrier_code','=',package_ref)])
                    if not package:
                        package = stock_quant_package_obj.create({'amazon_carrier_code' : package_ref})
                    package.write({'packaging_id' : product_package.id,
                                   'amazon_package_weight' : float(weight),
                                   'package_type' : package_type})
                product = product_product_obj.search([('default_code','=',default_code)])
                move_lines = stock_move_obj.search([('picking_id','=',picking_id.id),('product_id','=',product.id),('state','in',('confirmed','assigned','partially_available'))])
                if not move_lines :
                    continue                
                qty_left = float(file_qty)
                qty_grouped={}
                for move in move_lines:
                    for quant in move.reserved_quant_ids:
                        key=(quant.owner_id.id,move.location_id.id,move.location_dest_id.id,move.product_id.id,move.product_id.uom_id.id,quant.package_id and quant.package_id.id or False)
                        if qty_grouped.has_key(key):
                            qty_grouped[key]+=quant.qty
                        else:
                            qty_grouped.update({key:quant.qty})
    
                for key, qty in qty_grouped.items():
                    if qty_left>qty:                                        
                        raise UserError("File Qty shuld be equal to reserved quantity")
                    else:
                        pack_op_qty=qty_left
                    pack_op=stock_pack_operation.with_context({'no_recompute':True}).create(
                        {
                                'product_qty':float(pack_op_qty) or 0,
                                'date':time.strftime('%Y-%m-%d'),
                                'location_id':key[1], 
                                'location_dest_id': key[2],
                                'product_id': key[3],
                                'product_uom_id': key[4], 
                                'qty_done':float(pack_op_qty) or 0,
                                'picking_id':picking_id.id,
                                'result_package_id':package and package.id or False,
                                'owner_id':key[0],
                                # 'package_id':key[5]
                         })   
                    pack_op_ids.append(pack_op.id)
                    package.write({'move_line_ids' : [(4,pack_op.id)]})
                    qty_left=qty_left-pack_op_qty                                 
                    if qty_left<=0.0:
                        break
                if qty_grouped and qty_left >0.0:
                    pack_op = stock_pack_operation.with_context({'no_recompute':True}).create(
                                                        {
                                                        'product_qty':qty_left or 0,
                                                        'date':time.strftime('%Y-%m-%d'),
                                                        'location_id':move.location_id and move.location_id.id or False, 
                                                        'location_dest_id': move.location_dest_id and move.location_dest_id.id or False,
                                                        'product_id': move.product_id and move.product_id.id or False,
                                                        'product_uom_id': move.product_id and move.product_id.uom_id and move.product_id.uom_id.id or False, 
                                                        'qty_done':qty_left or 0,
                                                        'picking_id':picking_id.id,
                                                        'result_package_id':package and package.id or False,
                                                        'owner_id':picking_id.owner_id.id
                                                        })
                
                    pack_op_ids.append(pack_op.id)
                    #package.write({'move_line_ids' : [(6,0,[pack_op.id])]})

                elif not qty_grouped:
                    for move in move_lines:
                        delivered_qty = move.product_uom_qty
                        qty_left = qty_left - delivered_qty 
                        if qty_left < 0:
                            delivered_qty = qty_left + delivered_qty 
                        pack_op = stock_pack_operation.with_context({'no_recompute':True}).create(
                                                            {
                                                            'product_qty':delivered_qty or 0,
                                                            'date':time.strftime('%Y-%m-%d'),
                                                            'location_id':move.location_id and move.location_id.id or False, 
                                                            'location_dest_id': move.location_dest_id and move.location_dest_id.id or False,
                                                            'product_id': move.product_id and move.product_id.id or False,
                                                            'product_uom_id': move.product_id and move.product_id.uom_id and move.product_id.uom_id.id or False, 
                                                            'qty_done':delivered_qty or 0,
                                                            'picking_id':picking_id.id,
                                                            'result_package_id':package and package.id or False,
                                                            'owner_id':False
                                                            })
                    
                        pack_op_ids.append(pack_op.id)
                        package.write({'move_line_ids' : [(4,pack_op.id)]})
                        if qty_left <= 0:
                            break 

        self.picking_id.write({'is_package_info_imported' : True})
        return True
    
    
#     
#     def _put_in_pack_ept(self,operation,package):
#         operation_ids = self.env['stock.pack.operation']
#         if float_compare(operation.qty_done, operation.product_uom_qty, precision_rounding=operation.product_uom_id.rounding) >= 0:
#             operation_ids |= operation
#         else:
#             quantity_left_todo = float_round(
#                 operation.product_uom_qty - operation.qty_done,
#                 precision_rounding=operation.product_uom_id.rounding,
#                 rounding_method='UP')
#             new_operation = operation.copy(
#                 default={'product_uom_qty':0, 'qty_done': operation.qty_done})
#             operation.write({'product_uom_qty': quantity_left_todo,'qty_done': 0.0})
#             new_operation.write({'product_uom_qty':operation.qty_done})
#             operation_ids |= new_operation
#         package and operation_ids.write({'result_package_id': package.id})
#         return True
        