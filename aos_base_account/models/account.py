# -*- coding: utf-8 -*- 
# Part of Odoo. See LICENSE file for full copyright and licensing details. 
from odoo import api, fields, models 
from datetime import datetime 

class AccountJournal(models.Model):
    ''' Defining a student information '''
    _inherit = "account.journal"

    type = fields.Selection(selection_add=[
            ('sale_advance', 'Advance Sale'),
            ('purchase_advance', 'Advance Purchase')])
    
    
class AccountInvoice(models.Model):
    ''' Defining a student information '''
    _inherit = "account.invoice"
    
    attn = fields.Char('Attention',size=64)
    signature = fields.Char('Signature', size=64)
    journal_bank_id = fields.Many2one('account.journal', string='Payment Method', domain=[('type', 'in', ('cash','bank'))])
    
# class AccountInvoiceLine(models.Model):
#     _inherit = 'account.invoice.line'
#     
#     def _get_price_tax(self):
#         for l in self:
#             l.price_tax = l.price_total - l.price_subtotal
#     
#     price_tax = fields.Monetary(string='Tax Amount', compute='_get_price_tax', store=False)
    