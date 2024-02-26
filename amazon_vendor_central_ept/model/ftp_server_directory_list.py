from odoo import models,fields,api,_


class AmazonDirectoryList(models.Model):
    _name = 'ftp.server.directory.list'
    _sql_constraints = [
        ('avc_directory_list_unique_ept', 'UNIQUE (name,path,ftp_server_id)',
         'The Server must be unique!'),
    ]

    
    name=fields.Char(string = 'Name')
    path = fields.Char(string = 'Path')
    ftp_server_id = fields.Many2one('vendor.ftp.server', string = 'FTP Server')