# -*- coding: utf-8 -*- 
# Part of Odoo. See LICENSE file for full copyright and licensing details. 
from odoo import api, fields, models 
from datetime import datetime 

class res_partner_bank(models.Model):
    _inherit = 'res.partner.bank'
    
    street = fields.Char('Address 1')
    street2 = fields.Char('Address 2')
    
class res_partner(models.Model): 
    _inherit = 'res.partner' 
    
    bank_ids = fields.One2many('res.partner.bank', 'partner_id', string='Banks', copy=False)
    property_account_payable_id = fields.Many2one('account.account', company_dependent=True,
        string="Account Payable", oldname="property_account_payable",
        domain="[('internal_type', '=', 'payable'), ('deprecated', '=', False)]",
        help="This account will be used instead of the default one as the payable account for the current partner",
        required=False)
    property_account_receivable_id = fields.Many2one('account.account', company_dependent=True,
        string="Account Receivable", oldname="property_account_receivable",
        domain="[('internal_type', '=', 'receivable'), ('deprecated', '=', False)]",
        help="This account will be used instead of the default one as the receivable account for the current partner",
        required=False)
    property_account_advance_receivable_id = fields.Many2one('account.account', company_dependent=True,
        string="Account DP Customer", 
        domain="[('internal_type', '=', 'other'), ('reconcile', '=', True)]",
        help="This account will be used instead of the default one as the receivable advance account for the current partner",
        required=False)
    property_account_advance_payable_id = fields.Many2one('account.account', company_dependent=True,
        string="Account DP Vendors",
        domain="[('internal_type', '=', 'other'), ('reconcile', '=', True)]",
        help="This account will be used instead of the default one as the payable advance account for the current partner",
        required=False)
    property_account_asset_leasing_id = fields.Many2one('account.account', company_dependent=True,
        string="Account Leasing Vendors",
        domain="[('internal_type', '=', 'payable'), ('reconcile', '=', True)]",
        help="This account will be used instead of the default one as the payable advance account for the current partner",
        required=False)
