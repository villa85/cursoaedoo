# -*- coding: utf-8 -*-

from odoo import models,fields,api,_
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from tempfile import NamedTemporaryFile
import base64
import logging
import time
import csv
from io import StringIO,BytesIO
from dateutil.relativedelta import relativedelta
_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model_create_multi
    def export_po_ack(self):
        """
        USE: export_po_ack method called from stock.picking's 'Export POA' button,
        based on stock.picking and Amazon PO's information it will create POA EDI file
        and send it to Amazon Vendor Central.
        :return: Boolean
        """

        avc_file_transaction_job_obj = self.env['avc.file.transaction.log']
        avc_transaction_log_obj = self.env['avc.transaction.log.line']
        vendor_id = self.sale_id.vendor_id

        client_conf = self.env['ftp.config']
        client_conf_id = client_conf.search([('name', '=', vendor_id.client.name)])
        _logger.info("Id cliente picking => %r" % client_conf_id.name.name)

        mismatch_product = self.sale_id.mismatch_product
        #self.action_assign()
        order_line_info = []
        error_line_info = []
        if self.move_lines:
            avc_file_process_job_vals = {
                    'message':'PO Acknowledgement Export',
                    'vendor_id':vendor_id.id,
                    'application':'sale_order_response',
                    'operation_type':'export',
                    'create_date':datetime.now(),
                    'company_id':self.env.user.company_id.id,
                    'sale_order_id':self.sale_id.id,
                }
            self.job_id = avc_file_transaction_job_obj.create(avc_file_process_job_vals)
        order_info = {
                'order_name' : self.sale_id.amazon_edi_order_id,
                'schedule_date' : self.min_date,
                
            }
        for line in self.move_lines:
            reserved_qty = line.reserved_availability
            order_qty = line.product_uom_qty
            amazon_line_code = line.procurement_id.sale_line_id.amazon_edi_line_code
            price_unit = line.procurement_id.sale_line_id.price_unit
            total_price = line.procurement_id.sale_line_id.price_subtotal
            reserved_qty_price = reserved_qty * price_unit
            backorder_qty = order_qty - reserved_qty
            cancel_qty = order_qty - reserved_qty
            avc_transaction_log_obj_id = avc_transaction_log_obj.search([
                ('product_id', '=', int(line.product_id)),
                ('sale_order_line_id', '=', int(line.procurement_id.sale_line_id))])
            line_info = {
                        'product_id' : line.product_id,
                        'ref_li' : avc_transaction_log_obj_id.ref_li,
                        'reserved_qty' : reserved_qty,
                        'order_qty' : order_qty,
                        'unit_price' : price_unit,
                        'total_price' : total_price,
                        'reserved_qty_price' : reserved_qty_price,
                        'amazon_line_code' : amazon_line_code,
                        'sale_line_id' : line.procurement_id.sale_line_id,
                        'is_mismatch' : False,
                        'amazon_edi_line_code_type' : line.procurement_id.sale_line_id.amazon_edi_line_code_type
                    }
            if mismatch_product == 'backorder' : 
                line_info.update({'backorder_qty' : backorder_qty})
            if mismatch_product == 'cancel' :
                line_info.update({'cancel_qty' : cancel_qty})
            order_line_info.append(line_info)
            
        mismatch_lines =  avc_transaction_log_obj.search([('sale_order_id', '=', self.sale_id.id), ('operation_type', '=', 'import'),('is_mismatch_detail', '=', True)])
        for mismatch_line in mismatch_lines:
            remark = mismatch_line.remark.split(':')
            error_line = {
                    'remark' : mismatch_line.remark,
                    'amazon_line_code' : remark[1],
                    'is_mismatch' : True,
                    'unit_price' : mismatch_line.price,
                    'amazon_edi_line_code_type' : remark[0],
                    'qty' : mismatch_line.processed_qty,
                    'ref_li' : mismatch_line.ref_li,
                }
            error_line_info.append(error_line)
        message_info = {
            'sender_id':self.sale_id.sender_id,
            'recipient_id':self.sale_id.recipient_id,
            'supplier_id':self.sale_id.supplier_id,
            'delivery_party_id':self.sale_id.delivery_party_id,
            'country_code':self.sale_id.country_code,
            'buyer_address':self.sale_id.buyer_address,
            'buyer_id':self.sale_id.buyer_id,
            'invoice_id':self.sale_id.invoice_id,
            'max_delivery_date':self.sale_id.max_delivery_date_ept or False,
            'delivery_date':self.sale_id.delivery_date_ept or False,
        }

        if client_conf_id:
            self.prepare_book_order_ship_notice(vendor_id, order_info, message_info, order_line_info,error_line_info)
        else:
            self.prepare_order_ship_notice(vendor_id, order_info, message_info, order_line_info,error_line_info)
            # self.process_file_and_prapare_order(file_read)

        # self.prepare_order_ship_notice(vendor_id, order_info, message_info, order_line_info,error_line_info)
        return True

    @api.model_create_multi
    def prepare_book_order_ship_notice(self, vendor_id, order_info, message_info, order_line_info,error_line_info):
        """
        USE: Generate EDI file based on provided information of
        Amazon PO, Sale Order, stock.picking's move_lines.
        :param instance_id: vendor_id or instance_id
        :param order_info: Sale Order information dictionary
        :param message_info: other required PO's information
        :param order_line_info: sale order line information
        :return: Boolean
        """
        vendor_qualifier = vendor_id.vendor_qualifier
        amazon_qualifier = vendor_id.amazon_qualifier
        file_order_ship = NamedTemporaryFile(delete=False)
        total_segment = 0
        po_ack_file_string = ""
        self.export_avc_line_id = []
        if not message_info.get('sender_id', False) or not message_info.get('recipient_id', False):
            raise expression.except_osv(_('Error'), _('Sender or recipient identifier not found.'))
        product_product_obj = self.env['product.product']
        sender_id = message_info.get('sender_id',False)
        recipient_id = message_info.get('recipient_id',False)
        seq_interchange = self.env['ir.sequence'].get('amazon.edi.purchase.order.response')

        po_ack_file_string = po_ack_file_string + "UNA:+.? '"
        total_segment += 1
        
        po_ack_file_string = po_ack_file_string + "UNB+UNOC:2+%s:%s+%s:%s+%s:%s+%s+++++EANCOM'"%(recipient_id,vendor_qualifier,sender_id,amazon_qualifier,time.strftime("%y%m%d"),time.strftime("%H%M"),str(seq_interchange))
        total_segment += 1
        
        seq = self.env['ir.sequence'].get('amazon.edi.ship.message.trailer')
        po_ack_file_string = po_ack_file_string + "UNH+%s+ORDRSP:D:96A:UN:EAN005'"%(str(seq))
        total_segment += 1
        
        po_ack_file_string = po_ack_file_string + "BGM+231+%s+29'"%(order_info.get('order_name',''))
        total_segment += 1
        
        po_ack_file_string = po_ack_file_string + "DTM+137:%s:102'"%(time.strftime("%Y%m%d"))
        total_segment += 1
        
        po_ack_file_string = po_ack_file_string + "RFF+ON:%s'" % (order_info.get('order_name', ''))
        total_segment += 1
        
        date_done = order_info.get('schedule_date', time.strftime("%Y%m%d"))
        date_done = datetime.strptime(date_done, '%Y-%m-%d %H:%M:%S')
        date_done = date_done.strftime("%Y%m%d")
        po_ack_file_string = po_ack_file_string + "DTM+171:%s:102'"%(date_done)
        total_segment += 1
        
        po_ack_file_string = po_ack_file_string + "NAD+BY+%s::9+++++++%s'"%(message_info.get('delivery_party_id',''),message_info.get('country_code'))
        total_segment += 1

        po_ack_file_string = po_ack_file_string + "NAD+SU+%s::9'" %(message_info.get('supplier_id',''))
        total_segment += 1
        
        po_ack_file_string = po_ack_file_string + "CUX+2:%s:9'"%(self.sale_id.currency_id.name)
        total_segment += 1

        line_no = 0
        for order_line in order_line_info:
            #_logger.info(order_line)
            line_no += 1
            product_id = order_line.get('product_id')
            product_product = self.env['product.product']
            product_product_id = product_product.search([('id', '=', product_id.id)])
            today = datetime.today()
            formato = "%Y-%m-%d"
            str_today = today.strftime(formato)
            if not product_product_id.fecha_publicacion_ok:
                date_publish = str_today
            else:
                date_publish = product_product_id.fecha_publicacion_ok
            #if (date_publish <= str_today) == True and product_product_id.sale_ok == True and product_product_id.purchase_ok == True:
            #Para que entren todos los productos
            if (date_publish <= str_today) == True:
                _logger.info(order_line)
                ref_li = order_line.get('ref_li')
                reserved_qty = order_line.get('reserved_qty',0.0)
                order_qty = order_line.get('order_qty',0.0)
                unit_price = order_line.get('unit_price')
                total_price = order_line.get('total_price')
                reserved_qty_price = order_line.get('reserved_qty_price')
                amazon_line_code = order_line.get('amazon_line_code')
                sale_line_id = order_line.get('sale_line_id',False) 
                is_mismatch = order_line.get('is_mismatch')
                backorder_qty = order_line.get('backorder_qty',0.0)
                cancel_qty = order_line.get('cancel_qty',0.0)
                amazon_edi_line_code_type = order_line.get('amazon_edi_line_code_type')
                tax_amount = sale_line_id.tax_id and sale_line_id.tax_id[0] and sale_line_id.tax_id.amount or 0.0
                
                avc_transaction_log_val = {}

                if amazon_edi_line_code_type == 'barcode':
                    po_ack_file_string = po_ack_file_string + "LIN+%s+5+%s:EN'"%(str(line_no),amazon_line_code)
                    total_segment += 1
                    po_ack_file_string = po_ack_file_string + "PIA+1+%s:SA'"%(amazon_line_code)
                    total_segment += 1
                if amazon_edi_line_code_type == 'sku':
                    po_ack_file_string = po_ack_file_string + "LIN+%s'"%(str(line_no))
                    total_segment += 1
                    po_ack_file_string = po_ack_file_string + "PIA+5+%s:SA'"%(amazon_line_code)
                    total_segment += 1

                if reserved_qty > 0.0 and backorder_qty == 0.0:
                    _logger.info(reserved_qty)
                    po_ack_file_string = po_ack_file_string + "QTY+12:%s'"%(int(reserved_qty))
                    total_segment += 1
                    avc_transaction_log_val.update({'export_qty':reserved_qty})
                    po_ack_file_string = po_ack_file_string + "QTY+21:%s'"%(int(order_qty))
                    total_segment += 1

                if backorder_qty > 0.0:
                    _logger_info(backorder_qty)
                    backorder_date = self.sale_id.max_delivery_date_ept
                    
                    #date_done = order_info.get('schedule_date', time.strftime("%Y%m%d"))
                    backorder_date = datetime.strptime(backorder_date, '%Y-%m-%d')
                    backorder_date = backorder_date.strftime("%Y%m%d")
                    
                    po_ack_file_string = po_ack_file_string + "QTY+12:%s'"%(int(reserved_qty))
                    total_segment +=1
                    po_ack_file_string = po_ack_file_string + "QTY+21:%s'"%(int(order_qty))
                    total_segment += 1
                    # po_ack_file_string = po_ack_file_string + "QTY+83:%s'"%(str(backorder_qty))
                    # total_segment += 1
                    po_ack_file_string = po_ack_file_string + "DTM+11:%s:102'" % (backorder_date)
                    total_segment += 1
                    avc_transaction_log_val.update({'export_qty':reserved_qty})

                if cancel_qty and cancel_qty > 0.0:
                    _logger.info(cancel_qty)
                    if self.partner_id.name == "The Book Depository Ltd Extended":
                        if product_product_id.sale_ok == True and product_product_id.purchase_ok == True:
                            po_ack_file_string = po_ack_file_string + "QTY+12:%s'"%(int(order_qty))
                            total_segment += 1
                            po_ack_file_string = po_ack_file_string + "QTY+21:%s'"%(int(order_qty))
                            total_segment += 1
                            avc_transaction_log_val.update({'skip_line':False,'export_qty':str(order_qty)})
                        else:
                            po_ack_file_string = po_ack_file_string + "QTY+12:0'"
                            total_segment += 1
                            po_ack_file_string = po_ack_file_string + "QTY+21:%s'"%(int(cancel_qty))
                            total_segment += 1
                            avc_transaction_log_val.update({'skip_line':True,'export_qty':str(reserved_qty)})

                    else:
                        po_ack_file_string = po_ack_file_string + "QTY+12:0'"
                        total_segment += 1
                        po_ack_file_string = po_ack_file_string + "QTY+21:%s'"%(int(cancel_qty))
                        total_segment += 1
                        avc_transaction_log_val.update({'skip_line':True,'export_qty':reserved_qty})
                
                po_ack_file_string = po_ack_file_string + "PRI+AAA:%s:'"%(unit_price)
                total_segment += 1

                po_ack_file_string = po_ack_file_string + "RFF+LI:%s'"%(ref_li)
                total_segment += 1
                
                # if tax_amount > 0.0:
                #     po_ack_file_string = po_ack_file_string + "TAX+7+VAT+++:::%s'"%(str(tax_amount))
                #     total_segment += 1

                avc_transaction_log_val.update({
                    'message':'Sale Order Line',
                    'remark':'sale order name %s' % (self.sale_id.name or ''),
                    'sale_order_id':self.sale_id.id,
                    'job_id':self.job_id.id,
                    'sale_order_line_id':sale_line_id.id,
                    'product_id':product_id.id,
                    'company_id':self.env.user.company_id.id,
                    'user_id':self.env.user.id,
                    'picking_state':'draft',
                    'application':'sale_order_response',
                    'processed_qty':str(order_qty),
                    'create_date':datetime.now(),
                    'operation_type':'export',
                    'price':unit_price,
                })
                res = self.job_id.transaction_log_ids.create(avc_transaction_log_val)
                self.export_avc_line_id.append(res)

        for line in error_line_info:
            line_no += 1
            amazon_line_code = line.get('amazon_line_code')
            ref_li = line.get('ref_li')
            is_mismatch = line.get('is_mismatch')
            unit_price = line.get('unit_price')
            remark = line.get('remark')
            amazon_edi_line_code_type = line.get('amazon_edi_line_code_type')
            qty = line.get('qty')
            if amazon_edi_line_code_type == 'barcode':
                po_ack_file_string = po_ack_file_string + "LIN+%s+7+%s:EN'" %(str(line_no),str(amazon_line_code))
                total_segment += 1
            if amazon_edi_line_code_type == 'SKU' :
                po_ack_file_string = po_ack_file_string + "LIN+%s+7'"%(str(line_no))
                total_segment += 1
                po_ack_file_string = po_ack_file_string + "PIA+5+%s:SA'"%(amazon_line_code)
                total_segment += 1
            po_ack_file_string = po_ack_file_string + "QTY+12:0'"
            total_segment += 1
            po_ack_file_string = po_ack_file_string + "QTY+21:%s'"%(int(qty))
            total_segment += 1
            po_ack_file_string = po_ack_file_string + "PRI+AAA:%s:CT:NTP'"%(str(unit_price))
            total_segment += 1
            po_ack_file_string = po_ack_file_string + "RFF+LI:%s'"%(ref_li)
            total_segment += 1
            # po_ack_file_string = po_ack_file_string + "TAX+7+VAT+++:::0'"
            # total_segment += 1

            avc_transaction_log_val = {
                'message':'Product not Found',
                'remark':' %s' % (remark),
                'sale_order_id':self.sale_id.id,
                'job_id':self.job_id.id,
                'product_id':product_id.id or False,
                'company_id':self.env.user.company_id.id,
                'user_id':self.env.user.id,
                'picking_state':'draft',
                'application':'sale_order_response',
                'export_qty':'0',
                'processed_qty':str(qty),
                'is_mismatch_detail':False if product_id else True,
                'skip_line':True,
                'create_date':datetime.now(),
                'operation_type':'export',
                'price':unit_price,
            }
            res = self.job_id.transaction_log_ids.create(avc_transaction_log_val)
            self.export_avc_line_id.append(res)
        
        
        po_ack_file_string = po_ack_file_string + "UNS+S'"
        total_segment += 1
        
        po_ack_file_string = po_ack_file_string + "CNT+2:%s'"%(str(line_no))
        total_segment += 1
        
        # seq = self.env['ir.sequence'].get('amazon.edi.ship.message.trailer')
        po_ack_file_string = po_ack_file_string + "UNT+%s+%s'"%(str(total_segment), str(seq))
        po_ack_file_string = po_ack_file_string + "UNZ+1+%s'"%(str(seq_interchange))
        
        output = StringIO()
        result=base64.b64encode(po_ack_file_string.encode())
        output.write(po_ack_file_string)
        output.seek(0)
        file_order_ship.write(output.read().encode())
        file_order_ship.close()
      
        filename = "%s_%s.%s"%(vendor_id.po_ack_file_export_prefix,self.sale_id.amazon_edi_order_id,vendor_id.vendor_code)
        
        upload_file_name = '%s_%s_%s_%s_%s_%s_%s_%s.%s' % (
            vendor_id.po_ack_file_export_prefix,self.sale_id.amazon_edi_order_id, datetime.now().day, datetime.now().month, datetime.now().year, datetime.now().hour,
            datetime.now().minute, datetime.now().second,vendor_id.vendor_code)
        vals = {
            'name':upload_file_name,
            'datas':result,
            'datas_fname':upload_file_name,
            'res_model':'avc.file.transaction.log',
            'type':'binary',
            'res_id':self.job_id.id,
        }
        self.job_id.write({'filename':upload_file_name})
        attachment = self.env['ir.attachment'].create(vals)
        self.job_id.message_post(body=_("<b>Sale Order Acknowledgement File</b>"), attachment_ids=attachment.ids)
        connection_id = False
        if vendor_id.is_production_environment:
            ftp_server_id = vendor_id.production_ftp_connection
            directory_id = vendor_id.production_po_ack_directory_id
        else :
            ftp_server_id = vendor_id.test_ftp_connection
            directory_id = vendor_id.test_po_ack_directory_id
        with vendor_id.get_edi_sending_interface(ftp_server_id,directory_id) \
                as edi_interface:
            edi_interface.push_to_ftp(filename, file_order_ship.name)
        self.sale_id.write({'amazon_order_ack_uploaded':True})
        self.write({'po_ack_uploaded' : True})
        for lines in self.export_avc_line_id:
            lines.write({'filename':upload_file_name})
        return True
