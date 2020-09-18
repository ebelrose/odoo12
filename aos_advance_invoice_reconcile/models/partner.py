# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval
from odoo import api, fields, models, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.multi
    def _advance_total(self):
        account_move_line = self.env['account.move.line']
        if not self.ids:
            self.total_receivable_advanced = 0.0
            self.total_payable_advanced = 0.0
            return True

        user_currency_id = self.env.user.company_id.currency_id.id
        user_company_id = self.env.user.company_id.id
        all_partners_and_children = {}
        all_partner_ids = []
        all_partner_rec_ids = []
        all_partner_pay_ids = []
        for partner in self:
            # price_total is in the company currency
            all_partners_and_children[partner] = self.search([('id', 'child_of', partner.id)])
            all_partner_ids += all_partners_and_children[partner].ids
            #print ("===all_partners_and_children===",all_partners_and_children[partner].mapped('property_account_advance_receivable_id'),all_partners_and_children[partner].mapped('property_account_advance_payable_id'))
            all_partner_rec_ids += all_partners_and_children[partner].mapped('property_account_advance_receivable_id') and [all_partners_and_children[partner].mapped('property_account_advance_receivable_id').id] or []
            all_partner_pay_ids += all_partners_and_children[partner].mapped('property_account_advance_payable_id') and [all_partners_and_children[partner].mapped('property_account_advance_payable_id').id] or []

        # searching account.invoice.report via the orm is comparatively expensive
        # (generates queries "id in []" forcing to build the full table).
        # In simple cases where all invoices are in the same currency than the user's company
        # access directly these elements

        # generate where clause to include multicompany rules
        #RECEIVABLE
        where_query_receivable = account_move_line._where_calc([
            ('partner_id', 'in', all_partner_ids), 
            ('account_id', 'in', all_partner_rec_ids),
            ('company_id', '=', user_company_id),
            ('reconciled', '=', False), 
        ])
        account_move_line._apply_ir_rules(where_query_receivable, 'read')
        from_clause, where_clause_receivable, where_receivable_clause_params = where_query_receivable.get_sql()
        query_receivable = """
                  SELECT SUM(credit-debit) as total_receivable, partner_id
                    FROM account_move_line
                   WHERE %s
                   GROUP BY partner_id
                """ % where_clause_receivable
        self.env.cr.execute(query_receivable, where_receivable_clause_params)
        price_receivable_totals = self.env.cr.dictfetchall()
        #PAYABLE
        where_query_payable = account_move_line._where_calc([
            ('partner_id', 'in', all_partner_ids), 
            ('account_id', 'in', all_partner_pay_ids),
            ('company_id', '=', user_company_id),
            ('reconciled', '=', False), 
        ])
        account_move_line._apply_ir_rules(where_query_payable, 'read')
        from_clause, where_clause_payable, where_payable_clause_params = where_query_payable.get_sql()
        # price_total is in the company currency
        query_payable = """
                  SELECT SUM(debit-credit) as total_payable, partner_id
                    FROM account_move_line
                   WHERE %s
                   GROUP BY partner_id
                """ % where_clause_payable
        self.env.cr.execute(query_payable, where_payable_clause_params)
        price_payable_totals = self.env.cr.dictfetchall()
        for partner, child_ids in all_partners_and_children.items():
            #print ('===price_receivable_totals===',partner,child_ids,price_payable_totals,price_receivable_totals)
            partner.total_receivable_advanced = sum(price['total_receivable'] for price in price_receivable_totals if price['partner_id'] in child_ids.ids)
            partner.total_payable_advanced = sum(price['total_payable'] for price in price_payable_totals if price['partner_id'] in child_ids.ids)
            
    total_receivable_advanced = fields.Monetary(compute='_advance_total', string="Total Down Payment (Receivable)",
        groups='account.group_account_invoice')
    total_payable_advanced = fields.Monetary(compute='_advance_total', string="Total Down Payment (Payable)",
        groups='account.group_account_invoice')
    
    
    @api.multi
    def action_view_partner_advances_receivable(self):
        self.ensure_one()
        action = self.env.ref('aos_advance_invoice_reconcile.action_advance_tree1_jvp').read()[0]
        action['domain'] = literal_eval(action['domain'])
        action['domain'].append(('partner_id', 'child_of', self.id))
        return action
    
    @api.multi
    def action_view_partner_advances_payable(self):
        self.ensure_one()
        action = self.env.ref('aos_advance_invoice_reconcile.action_advance_tree2_jvp').read()[0]
        action['domain'] = literal_eval(action['domain'])
        action['domain'].append(('partner_id', 'child_of', self.id))
        return action