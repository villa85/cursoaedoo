# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class vendor_config(models.Model):
    _inherit = 'amazon.vendor.instance'

    client = fields.Many2one('res.partner',string="Client")



class avc_trasaction_log_config(models.Model):
    _inherit = 'avc.transaction.log.line'

    ref_li = fields.Text("Reference Line")