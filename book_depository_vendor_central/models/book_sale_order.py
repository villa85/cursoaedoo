# -*- coding: utf-8 -*-

import base64
from io import StringIO
import csv
import logging
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tempfile import NamedTemporaryFile
from odoo import models, fields, api, _
from odoo.osv import expression
#from pdf417gen import encode, render_image
_logger = logging.getLogger(__name__)

class sale_order(models.Model):
    _inherit = "sale.order"

    @api.model_create_multi
    def import_sales_from_amazon_edi(self, vendor_ids = None,file_data=None):
        """
        Use: Fetch the sale orders file from FTP location,
            format the data into format required by Odoo
            and create the sale in Odoo
        :param vendor_id: Amazon Vendor Central Instance ID
        :param file_data: EDI 850 Purchase Order file
        :return: Boolean
        """
        client_conf = self.env['ftp.config']
        client_conf_id = client_conf.search([('name', '=', vendor_ids.client.id)])

        ctx = self._context.copy() or {}

        for vendor in vendor_ids:
            self.job_id = None
            self.filename = None
            self.server_filename = None
            self.export_avc_line_id = []
            self.ack_error_lines=[]

            filenames_dict ={}
            if file_data:
                imp_file = StringIO(base64.decodestring(file_data))
                file_write = open('/tmp/order_data.txt','wb')
                file_write.writelines(imp_file.getvalue())
                file_write.close()
                file_read = open('/tmp/order_data.txt', "rU")
                dialect = csv.Sniffer().sniff(file_read.readline())
                file_read.seek(0)
                reader = csv.reader(file_read,delimiter="'",quotechar='|')
                file_read.seek(0)
                if client_conf_id:
                    self.process_book_file_and_prapare_order(file_read)
                else:
                    self.process_file_and_prapare_order(file_read)
                # self.process_file_and_prapare_order(file_read)
            else:
                file_to_delete = []
                connection_id = False
                if vendor.is_production_environment:
                    ftp_server_id = vendor.production_ftp_connection
                    directory_id = vendor.production_po_directory_id
                else :
                    ftp_server_id = vendor.test_ftp_connection
                    directory_id = vendor.test_po_directory_id

                with vendor.get_edi_receive_interface(ftp_server_id,directory_id) \
                            as edi_interface:
                    # `filenames` contains a list of filenames to be imported 
                    filenames_dict = edi_interface.pull_from_ftp(vendor.po_file_import_prefix) 
                            
                for server_filename, filename in filenames_dict.items():
                    
                    with open(filename) as file:
                        self.job_id = None
                        self.filename = filename
                        self.server_filename = server_filename
                        ctx.update({'filename':server_filename})
                        if client_conf_id:
                            self.process_book_file_and_prapare_order(vendor,file)
                        else:
                            self.process_file_and_prapare_order(vendor,file)
                        # self.process_file_and_prapare_order(vendor,file)
                    file_to_delete.append(server_filename) #  : Ekta
                    
                    if self.job_id:
                        binary_package = open(filename).read().encode()
                        attachment_vals = {
                            'name':server_filename,
                            'datas':base64.encodestring(binary_package),
                            'datas_fname':server_filename,
                            'type':'binary',
                            'res_model': 'avc.file.transaction.log',
                            'res_id':self.job_id.id,
                            }
                        
                        attachment=self.env['ir.attachment'].create(attachment_vals)
                        self.job_id.write({'attachment_id' : attachment.id})
                        self.job_id.message_post(body=_("<b>PO Import File</b>"),attachment_ids=attachment.ids)
                        self.job_id.message_post(body=_(("<b>Sale Order created %s</b>"%(self.order_id.name or '') if self.order_id else "<b>Information Mismatch</b>")))
                        if vendor.auto_confirm_sale_order and self.job_id.sale_order_id:
                            self.auto_send_poa(vendor,self.job_id.sale_order_id)

                if file_to_delete:
                    with vendor.get_edi_receive_interface(ftp_server_id,directory_id) \
                                as edi_interface:
                        # `filenames` contains a list of filenames to be imported
                        edi_interface.sftp_client.chdir(edi_interface.download_dir)# :EKta
                        for filename in file_to_delete:
                            edi_interface.delete_from_ftp(filename)
        return True

    @api.model_create_multi
    def process_book_file_and_prapare_order(self,vendor,file):
        """
        Use: Decode Amazon EDI 850 Purchase Order file and create sale order, sale order lines and required log entries.
        :param file: EDI 850 Purchase Order file
        :return: Boolean
        """
        #declaration
        country_obj = self.env['res.country']
        partner_obj = self.env['res.partner']      
        sale_order_obj = self.env['sale.order']  
        sale_order_line_obj = self.env['sale.order.line']
        product_product_obj = self.env['product.product']
        
        delivery_address = {}
        order_line_info = {}
        inv_address_data = {}
        order_info = {}
        message_info = {}  
        line_no = 1
        order_line = 0
        total_segment = 0
        self.order_type = ''
        
        #read and seprate file in diffrent part
        for segment in csv.reader(file,delimiter="'",quotechar='|'):
            for seg  in segment:
                if seg.startswith('UNB+UNOA') or seg.startswith('UNB+UNOC'):
                    header = seg.split("+")
                    message_info.update({'sender_id' : header[2],'recipient_id' : header[3]})
                    total_segment +=1
                    
                elif seg.startswith('UNH'):
                    msg_type = seg.split("+")
                    msg_type = msg_type[2].split(":")[0] if len(msg_type)>2 else ''
                    message_info.update({'message_type' : msg_type})
                    total_segment +=1
                    
                elif seg.startswith('BGM+'):
                    order_name = seg.split("+")
                    order_name = order_name[2] if len(order_name) >= 3 else ''
                    order_info.update({'order_name':order_name})
                    total_segment +=1

                elif seg.startswith('FTX+GEN'):
                    total_segment +=1
                     
                elif seg.startswith('DTM+137'):
                    date_seg = seg.split(":")
                    date_order = datetime.strptime(date_seg[1], '%Y%m%d')
                    order_info.update({'date_order':date_order,
                        'delivery_date':date_order})
                    total_segment +=1

                elif seg.startswith('DTM+171'):
                    total_segment +=1

                elif seg.startswith('RFF+ON'):
                    total_segment +=1
                     
                elif seg.startswith('NAD+ST') or seg.startswith('NAD+BY'):
                    buyer_id = seg.split(":")
                    buyer_address = buyer_id[0][7:]+':'+buyer_id[2]
                    buyer_id = buyer_id and buyer_id[0][7:]

                    client = self.env['res.partner']
                    client_id = client.search([('edi_gln_no', '=', buyer_id)])
                    if client_id.parent_id:
                        parent_id = client_id.parent_id
                    else:
                        parent_id = client_id.id

                    country = self.env['res.country']
                    country_id = country.search([('id', '=', client_id.country_id.id)])

                    inv_address_data = {
                        'type':'invoice',
                        'name': str(client_id.name),
                        'street': str(client_id.street),
                        'city': str(client_id.city),
                        'zip': str(client_id.zip),
                        'country_id': country_id.id,
                        'parent_id': parent_id,
                        }
                    
                    message_info.update({'buyer_id':buyer_id,'buyer_address':buyer_address, 
                        'delivery_party_id':buyer_id,'country_code':country_id.id,
                        'invoice_id':buyer_id})
                    order_info.update({'inv_address_data':inv_address_data,
                        'delivery_address':inv_address_data})                    
                    total_segment +=1
                    continue
                
                elif seg.startswith('NAD+SU'):
                    supplier_id = seg.split(":")
                    supplier_id = supplier_id and supplier_id[0][7:]
                    message_info.update({'supplier_id':supplier_id})
                    total_segment +=1
                    continue
                
                elif seg.startswith('CUX+2'):
                    currancy = seg.split(":")
                    currancy_code = currancy[1]
                    currency_id = self.env['res.currency'].search([('name','=',currancy_code)])
                    currency_id = currency_id and currency_id[0] or False
                    pricelist_id = vendor and vendor.pricelist_id or False
                    pricelist_id = pricelist_id and pricelist_id.id or False
                    order_info.update({'currency_id':currency_id.id,'pricelist_id':pricelist_id})
                    message_info.update({'currancy_code':currancy_code})
                    total_segment +=1
                    continue
                #sale order line data saprate here
                elif seg.startswith('LIN+'):
                    order_line_info.update({'Line_'+str(line_no):{}})
                    order_line_info['Line_'+str(line_no)].update({'price':0})
                    ean = seg.split("+")
                    ean = ean[len(ean)-1] 
                    if ean.upper().find('EN',0,len(ean)) !=-1 and ean.upper().find(':',0,len(ean)) !=-1:
                        ean = ean.split(":") and ean.split(":")[0] or ''
                        order_line_info['Line_'+str(line_no)].update({'ean':ean})
                    #UP used for Universal Product Code **code edited here**
                    elif ean.upper().find('UP',0,len(ean)) !=-1 and ean.upper().find(':',0,len(ean)) !=-1:
                        ean = ean.split(":") and ean.split(":")[0] or ''
                        order_line_info['Line_'+str(line_no)].update({'ean':ean})
                    
                    product_price = self.env['product.template']
                    price = product_price.search([('barcode', '=', ean)])
                    line_no += 1
                    order_line_info['Line_'+str(line_no-1)].update({'price':price.list_price})

                    # line_no += 1
                    order_line +=1
                    total_segment +=1
                    
                elif seg.startswith('PIA+'):
                    code = seg.split("+") 
                    code = code[2][:-3] if len(code)>2 else ''
                    if not order_line_info['Line_'+str(line_no-1)].get('ean',False):
                        order_line_info['Line_'+str(line_no-1)].update({'default_code':code})
                    total_segment +=1

                elif seg.startswith('QTY+21'):
                    qty = seg.split(":") 
                    qty = qty[1] if len(qty)>1 else 0
                    order_line_info['Line_'+str(line_no-1)].update({'qty':qty})
                    total_segment +=1

                elif seg.startswith('RFF+LI'):
                    ref = seg.split(":") 
                    ref = ref[1] if len(ref)>1 else 0
                    order_line_info['Line_'+str(line_no-1)].update({'ref':ref})
                    total_segment +=1
                                          
                elif seg.startswith('UNS+S'):
                    total_segment +=1
                    
                elif seg.startswith('CNT+2'):
                    total_line = seg.split(":") 
                    total_line = total_line[1] if len(total_line)>1 else 0
                    total_segment +=1
                    
                    if int(total_line) != order_line:
                        raise expression.except_osv(_('Error'), _('Order Line not integrated properly, Please Check order line data in file.'))                                                
                    
                elif seg.startswith('UNT+'):
                    segments = seg.split("+")
                    segments = segments[1]
                    if int(segments) != total_segment:
                        raise expression.except_osv(_('Error'), _('File not integrated properly, Please Check file data.'))

        if not vendor.supplier_id == message_info.get('supplier_id', ''):
            if not self.job_id:
                avc_file_process_job_vals = {
                    'message':'Mismatch Supplier Information',
                    'filename':self.server_filename,
                    'vendor_id':vendor.id,
                    'application':'sale_order',
                    'operation_type':'import',
                    'create_date':datetime.now(),
                    'company_id':vendor.company_id.id or False,
                }
                self.job_id = self.create_avc_file_process_job(avc_file_process_job_vals)
            return True
        
        if not vendor.pricelist_id.currency_id.id == order_info.get('currency_id'):
            order_info.update({'currency_id':vendor.pricelist_id.currency_id.id,'pricelist_id':vendor.pricelist_id.id})
            message_info.update({'currancy_code':vendor.pricelist_id.currency_id.name})


            # if not self.job_id:
            #     avc_file_process_job_vals = {
            #         'message':'Mismatch Pricelist information',
            #         'filename':self.server_filename,
            #         'vendor_id':vendor.id,
            #         'application':'sale_order',
            #         'operation_type':'import',
            #         'create_date':datetime.now(),
            #         'company_id':vendor.company_id.id or False,
            #     }
            #     self.job_id = self.create_avc_file_process_job(avc_file_process_job_vals)
            # return True
        
        #checked if order exist or not
        existing_order_id = sale_order_obj.search([('amazon_edi_order_id', '=', order_info.get('order_name', ''))])
        if self.order_type == 'firstorder':
            if existing_order_id:
                return True

        #message_id = self.env['amazon.edi.message.info'].create(message_info)        
        order_vals = self.prepare_book_order_vals(vendor,order_info,message_info.get('delivery_party_id',False))
        order_vals.update({'vendor_id':vendor.id,'account_type':self.order_type, 'carrier_id':vendor.amazon_edi_carrier_method.id or False})
        order_vals.update(message_info)
        if vendor.warehouse_id : 
            order_vals.update({'warehouse_id':vendor.warehouse_id.id})
        order_id = sale_order_obj.create(order_vals)
        #message_id.write({'order_id':order_id.id})
        #self.order_id = order_id 
        fiscal_position_id = order_vals.get('fiscal_position_id',False)
        fiscal_position = self.env['account.fiscal.position'].browse(fiscal_position_id) or False        
        line_id = False
        
        #CREATE LOG IN avc.file.transaction.log
        avc_file_process_job_vals = {
                        'message': 'Order imported',
                        'filename': self.server_filename,
                        'vendor_id': vendor.id,
                        'application' : 'sale_order',
                        'operation_type' : 'import',
                        'create_date' : datetime.now(),
                        'company_id':vendor.company_id.id or False,
                        'sale_order_id':order_id.id,
                        }
        self.job_id = self.create_avc_file_process_job(avc_file_process_job_vals)
        
        for key,value in order_line_info.items():
            default_code = value.get('default_code',False)
            ean = value.get('ean',False)
            product = False
            if default_code:
                product = product_product_obj.search([('amazon_sku','=',default_code)])
                if not product :
                    product = product_product_obj.search([('default_code','=',default_code)]) 
                code_type="SKU"
                amazon_code = default_code
                amazon_edi_line_code_type = 'sku'
            if ean :
                product = product_product_obj.search([('barcode','=',ean)])
                code_type = "barcode"
                amazon_code = ean
                amazon_edi_line_code_type = 'barcode'
            orderlinevals ={}
            line=()
            ref_li = value.get('ref',0) 
            if product:
                qty = value.get('qty',0.0)
                price = value.get('price',0.0) 
                line=(product,price,amazon_code,qty)
                
                orderlinevals,product_id, qty_code = self.prepare_order_line_vals(line,order_id)
                orderlinevals.update({'amazon_edi_line_code_type' : amazon_edi_line_code_type})
                line = ()
                if orderlinevals:
                    sale_order_line_id = sale_order_line_obj.create(orderlinevals)
                    
                    avc_transaction_log_val = {
                        'message':'Sale Order Line Created',
                        'remark':'sale order id %s'%(order_id.name or ''),
                        'sale_order_id':order_id.id,
                        'job_id':self.job_id.id,
                        'picking_id':False,
                        'back_order_id':False,
                        'sale_order_line_id':sale_order_line_id.id,
                        'product_id':orderlinevals.get('product_id',''),
                        'package_id':False,
                        'stock_inventory_id':False,
                        'company_id':self.job_id.company_id.id or False,
                        'user_id':self.env.user.id,
                        'picking_state':'draft',
                        'application':'sale_order',
                        'export_qty':orderlinevals.get('product_uom_qty',''),
                        'processed_qty':orderlinevals.get('product_uom_qty',''),
                        'manually_processed':False,
                        'is_mismatch_detail':False,
                        'skip_line':False,
                        'skip_order':False,
                        'ref_li':ref_li,
                        'filename':self.server_filename,
                        'create_date':datetime.now(),
                        'operation_type':'import',
                        'price':price,
                        }
                    self.job_id.transaction_log_ids.create(avc_transaction_log_val)
                else:
                    line = line + (False,qty_code)
                    self.ack_error_lines.append(line)
                    self.create_book_avc_transaction_lines(order_id,code_type='SKU',code=code,processed_qty=qty,msg='Product not found',price=price, ref=ref_li)
            else:
                qty_code = 182
                line = line + (False,qty_code)
                self.ack_error_lines.append(line)
                self.create_book_avc_transaction_lines(order_id,code_type='barcode',code=amazon_code,processed_qty=qty,msg='Product not found',price=price, ref=ref_li)
        return True


    @api.model_create_multi
    def create_book_avc_transaction_lines(self,order,code_type=None,code=None,processed_qty=None,msg=None,price=None,product_id=None, ref=None):
        """
        Use: To create avc.transaction.log.line new line.
        :param code_type: code information sku/barcode
        :param code: code data
        :param processed_qty: ordered quantity
        :param msg: message for log line
        :param price: price ordered product
        :param product_id: product id if available
        :return: avc.transaction.log.line's id
        """
        #it make an entry in avc.transaction.log.line
        avc_transaction_log_val = {
                    'message':msg if msg else 'Product not Found',
                    'remark': '%s:%s'%(code_type,code),
                    'sale_order_id':order.id,
                    'job_id':self.job_id.id,
                    'company_id':self.job_id.company_id.id or False,
                    'user_id':self.env.user.id,
                    'application':'sale_order',
                    'export_qty':0.0,
                    'processed_qty':processed_qty,
                    'manually_processed':False,
                    'is_mismatch_detail':False if product_id else True,
                    'skip_line':True,
                    'skip_order':False,
                    'ref_li':ref,
                    'filename':self.server_filename,
                    'create_date':datetime.now(),
                    'operation_type':'import',
                    'price':price,
                    'product_id':product_id if product_id else False,
                    }
        res = self.job_id.transaction_log_ids.create(avc_transaction_log_val)
        return res

    @api.model_create_multi
    def prepare_book_order_vals(self,vendor,order_info,delivery_party_id):
        """
        Use: To generate sale order's value based on given information.
        :param order_info: Sale Order required information
        :param delivery_party_id: Delivery Party ID
        :return: sale order values (dict{})
        """
        sale_order_obj = self.env['sale.order']
        partner_obj = self.env['res.partner']
        address_data = order_info.get('inv_address_data',{})
        delivery_address = order_info.get('delivery_address',{})
        partner_id=address_data.get('parent_id',False)
        if not partner_id:
            return
        
        inv_add_domain=[]
        for address in address_data:
            inv_add_domain.append((address,'=',address_data.get(address)))
        
        delivert_add_domain=[]
        for address in delivery_address:
            delivert_add_domain.append((address,'=',delivery_address.get(address)))

        inv_add_id = partner_obj.search(inv_add_domain)
        inv_add_id = inv_add_id and inv_add_id[0]        
        if not inv_add_id:
            inv_add_id = partner_obj.create(address_data)

        delivery_add_id = partner_obj.search(delivert_add_domain)
        delivery_add_id = delivery_add_id and delivery_add_id[0]
        if not delivery_add_id:
            delivery_add_id = partner_obj.create(delivery_address)
        
        delivery_id = partner_obj.search([('edi_gln_no','=',delivery_party_id),('parent_id','=',partner_id)])
        if not delivery_id:
            delivery_id = partner_obj.search([('edi_gln_no','=',delivery_party_id)])
            if delivery_id and delivery_id.id != partner_id:
                delivery_id.write({'parent_id':partner_id})
            else:
                partner_obj.browse(partner_id).write({'edi_gln_no': delivery_party_id})

        partner_address = partner_obj.browse(partner_id).address_get(['contact','invoice','delivery'])

        ordervals={
                   'company_id':vendor.company_id.id or False,
                   'partner_id' :partner_id,
                   }
        new_record = sale_order_obj.new(ordervals)
        new_record.onchange_partner_id()
        ordervals = sale_order_obj._convert_to_write({name: new_record[name] for name in new_record._cache})
        new_record = sale_order_obj.new(ordervals)
        new_record.onchange_partner_shipping_id()
        ordervals = sale_order_obj._convert_to_write({name: new_record[name] for name in new_record._cache})
        ordervals.update({
                        'name' : order_info.get('order_name'),
                        'amazon_edi_order_id' : order_info.get('order_name',''),
                        'picking_policy' : vendor.picking_policy or False,
                        'date_order' : order_info.get('date_order',False) and order_info['date_order'].strftime('%Y-%m-%d') or time.strftime('%Y-%m-%d'),
                        'state' : 'draft',
                        #'invoice_status' : self.instance_id.amazon_edi_invoice_status or 'invoiced',
                        'mismatch_product' : vendor.mismatch_product,
                        'is_amazon_edi_order' : True,
                        'note': order_info.get('order_name',''),
                        'client_order_ref' : order_info.get('order_name',''),
                        'pricelist_id': order_info.get('pricelist_id',False),
                    })
        return ordervals