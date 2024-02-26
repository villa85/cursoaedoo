from odoo import models,fields,api,_
from odoo.exceptions import ValidationError,UserError
from .amazon_edi_interface import AmazonEDIInterface
import base64

class vendor_ftp_server(models.Model):
    _name="vendor.ftp.server"

     
    name=fields.Char(string = "Name",copy=False)
    connection_type = fields.Selection([('test_connection','Test Connection'),('production_connection','Production Connection')], string = 'Connection Type')
    ftp_host = fields.Char("FTP Host")
    ftp_port = fields.Char("FTP Port")
    ftp_key_location = fields.Char("FTP Key location")
    receive_ftp_user = fields.Char("FTP User")
    receive_ftp_password = fields.Char("FTP Password")
    sending_ftp_user = fields.Char("FTP User")
    sending_ftp_password = fields.Char("FTP Password")
    directory_ids =fields.One2many('ftp.server.directory.list','ftp_server_id','FTP Server')

    _sql_constraints = [
         ('vendor_ftp_server_unique_ept', 'unique(name)',
          'The Server Name must be unique!'),
    ]
    
             
    def create_ftp_server(self):
        self.do_test_connection()
        return True
    
    
    def do_test_connection(self):
        sending_ftp_user = self.sending_ftp_user
        sending_pswd = self.sending_ftp_password
        receive_ftp_user = self.receive_ftp_user
        receive_pswd = self.receive_ftp_password

        ftp_host = self.ftp_host + ':' + self.ftp_port
        sending_key_location = self.ftp_key_location
        try :
            if not self.directory_ids:
                raise Warning("Please add FTP directories")
            for direcotry in self.directory_ids:
                sending = AmazonEDIInterface(
                    ftp_host,
                    sending_ftp_user,
                    sending_pswd,
                    sending_key_location,
                    upload_dir = direcotry.path,
                )
                receive = AmazonEDIInterface(
                    ftp_host,
                    receive_ftp_user,
                    receive_pswd,
                    sending_key_location,
                    download_dir = direcotry.path,
                )
            if sending or receive:
                raise Warning("Working properly")
            else :
                raise Warning("Not woking")
        except Exception as e:
            raise Warning(_("%s") % e)
        
    
     
   