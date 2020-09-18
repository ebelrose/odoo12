# -*- coding: utf-8 -*- 
# Part of Odoo. See LICENSE file for full copyright and licensing details. 
from odoo import api, fields, models, _
from datetime import datetime 
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError, ValidationError

TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_invoice_advance': 'sale_advance',
    'in_invoice_advance': 'purchase_advance',
}
# mapping invoice type to refund type
TYPE2REFUND = {
    'out_invoice': 'out_refund',        # Customer Invoice
    'in_invoice': 'in_refund',          # Vendor Bill
    'out_refund': 'out_invoice',        # Customer Credit Note
    'in_refund': 'in_invoice',          # Vendor Credit Note
}

TYPE2JOURNALADV = {
    'out_invoice': 'sale_advance',
    'in_invoice': 'purchase_advance',
    'out_refund': 'sale_advance',
    'in_refund': 'purchase_advance',
}

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    line_to_reconcile_id = fields.Many2one('account.move.line', 'Line to Reconcile')
    
class AccountInvoice(models.Model): 
    _name = 'account.invoice'
    _inherit = ['account.invoice','mail.thread', 'mail.activity.mixin', 'portal.mixin']
    
    @api.one
    @api.depends('advance_line_ids.move_check')
    def _compute_amount_advance(self):
        self.amount_advance = sum(line.move_check and line.base for line in self.advance_line_ids)
    
    @api.model
    def _default_journal(self):
        if self._context.get('default_journal_id', False):
            return self.env['account.journal'].browse(self._context.get('default_journal_id'))
        inv_type = self._context.get('type', 'out_invoice')
        if self._context.get('is_advance'):
            inv_type = inv_type + '_advance'
        inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [
            ('type', 'in', [TYPE2JOURNAL[ty] for ty in inv_types if ty in TYPE2JOURNAL]),
            ('company_id', '=', company_id),
        ]
        return self.env['account.journal'].search(domain, limit=1)
    
    type = fields.Selection(selection_add=[('out_invoice_advance','Sale Advance'),('in_invoice_advance','Purchase Advance')])
    product_id = fields.Many2one('product.product', related='invoice_line_ids.product_id', string='Product')
    is_advance = fields.Boolean('Is Advance', default=lambda self: self._context.get('is_advance', False))
    is_asset = fields.Boolean('Is Asset', default=lambda self: self._context.get('is_asset', False))
    
    account_advance_id = fields.Many2one('account.account', string='Account Advance',
        required=False, readonly=True, states={'draft': [('readonly', False)]},
        domain=[('deprecated', '=', False)], help="The partner account advance used for this invoice.")
    
    advance_line_ids = fields.One2many('account.advance.line', 'invoice_id', 'Advance Line')
    journal_id = fields.Many2one('account.journal', string='Journal',
        required=True, readonly=True, states={'draft': [('readonly', False)]},
        default=_default_journal,
        domain="[('type', 'in', {'out_invoice': ['sale','sale_advance'], 'out_refund': ['sale_refund'], 'in_refund': ['purchase_refund'], 'in_invoice': ['purchase','purchase_advance']}.get(type, [])), ('company_id', '=', company_id)]")
    amount_advance = fields.Monetary(string='Advance Amount', digits=dp.get_precision('Account'),                 
        store=True, readonly=True, compute='_compute_amount_advance')

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        res = super(AccountInvoice, self)._onchange_partner_id()
        if self.type == 'out_invoice' and self.partner_id.property_account_advance_receivable_id:
            self.account_advance_id = self.partner_id.property_account_advance_receivable_id.id
        elif self.type == 'in_invoice' and self.partner_id.property_account_advance_payable_id:
            self.account_advance_id = self.partner_id.property_account_advance_payable_id.id
        return res
    
    @api.multi
    def action_move_create(self):
        result = super(AccountInvoice, self).action_move_create()
        #===========================================================
        # ADVANCE
        #===========================================================
        ar_account_ids = self.move_id.line_ids.filtered(lambda r: r.account_id == self.account_id)
        if self.advance_line_ids:
            for adv_line in self.advance_line_ids:
                if adv_line.move_check:
                    adv_account_ids = adv_line.move_line_id                    
                    advance_aml_ids = self._create_advance_entry(adv_line)
                    adv_to_reconcile = adv_account_ids+advance_aml_ids[0]
                    adv_to_reconcile.reconcile()
                    ar_account_ids += advance_aml_ids[1]
            ar_account_ids.reconcile()
        return result
    
    def _get_advance_vals(self, journal=None):
        """ Return dict to create the payment move"""
        journal = journal or self.journal_id
        if not journal.sequence_id:
            raise UserError(_('Configuration Error !'), _('The journal %s does not have a sequence, please specify one.') % journal.name)
        if not journal.sequence_id.active:
            raise UserError(_('Configuration Error !'), _('The sequence of journal %s is deactivated.') % journal.name)
        name = journal.with_context(ir_sequence_date=self.date_invoice).sequence_id.next_by_id()
        return {
            'name': name,
            'date': self.date_invoice,
            'ref': 'RECONCILE: '+self.move_name or '',
            'company_id': self.company_id.id,
            'journal_id': journal.id,
        }
    
    def _get_shared_move_line_vals(self, debit, credit, amount_currency, move_id, invoice_id=False):
        """ Returns values common to both move lines (except for debit, credit and amount_currency which are reversed)"""
        return {
            'partner_id': self.env['res.partner']._find_accounting_partner(self.partner_id).id or False,
            'invoice_id': self.id or False,
            'move_id': move_id,
            'debit': debit,
            'credit': credit,
            'amount_currency': amount_currency or False,
        }
        
    def _create_advance_entry(self, adv_line):
        """ Create the journal entry corresponding to the 'incoming money' part of an internal transfer, return the reconciliable move line"""
        aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
        if self.type in ('out_invoice', 'out_refund'):
            debit, credit, amount_currency, dummy = aml_obj.with_context(date=self.date_invoice)._compute_amount_fields(adv_line.base, self.currency_id, self.company_id.currency_id)
            debit_adv, credit_adv, amount_currency_adv, dummy_adv = aml_obj.with_context(date=adv_line.move_line_id.date)._compute_amount_fields(adv_line.base, self.currency_id, self.company_id.currency_id)
        else:
            credit, debit, amount_currency, dummy = aml_obj.with_context(date=self.date_invoice)._compute_amount_fields(adv_line.base, self.currency_id, self.company_id.currency_id)
            credit_adv, debit_adv, amount_currency_adv, dummy_adv = aml_obj.with_context(date=adv_line.move_line_id.date)._compute_amount_fields(adv_line.base, self.currency_id, self.company_id.currency_id)
        amount_currency = adv_line.journal_id.currency_id and self.currency_id.with_context(date=self.date_invoice).compute(adv_line.base, adv_line.journal_id.currency_id) or 0
        #amount_invoice_currency = adv_line.journal_id.currency_id and self.currency_id.with_context(date=self.date_invoice).compute(adv_line.base, adv_line.journal_id.currency_id) or 0
        #print "=====debit, credit, amount_currency, dummy====",adv_line,debit_adv, credit_adv, amount_currency_adv, dummy_adv
        #print "=====debit_inv, credit_inv, amount_currency_inv, dummy_inv====",debit_adv, credit_adv, amount_currency_adv, dummy_adv
        dst_move = self.env['account.move'].create(self._get_advance_vals(adv_line.journal_id))
        dacc = self.account_advance_id.id
        cacc = self.account_id.id
        if self.type in ('out_invoice', 'out_refund') and self.account_advance_id and not adv_line.move_line_id.reconciled:
            nadv = 'CADV'
            ninv = 'CINV'
        else:
            nadv = 'SADV'
            ninv = 'SINV'
        get_name = ''
        if self.origin:
            get_name = self.origin
            
        advance_aml_dict = self._get_shared_move_line_vals(debit_adv, credit_adv, amount_currency_adv, dst_move.id)
        advance_aml_dict.update({
            'name': _('%s:%s:%s') % (nadv,self.move_id.name, get_name),
            'account_id': dacc,
            'currency_id': adv_line.journal_id and adv_line.journal_id.currency_id.id or adv_line.invoice_id.currency_id and adv_line.invoice_id.currency_id.id,
            'journal_id': adv_line.journal_id and adv_line.journal_id.id or adv_line.invoice_id.journal_id and adv_line.invoice_id.journal_id.id,
            'line_to_reconcile_id': adv_line.move_line_id.id})
        if self.currency_id != self.company_id.currency_id:
            advance_aml_dict.update({
                'currency_id': self.currency_id.id,
                'amount_currency': debit_adv > 0 and adv_line.base or -adv_line.base,
            })
        #print ("====self.currency_id != self.company_id.currency_id====",advance_aml_dict)
        advance_aml = aml_obj.create(advance_aml_dict)
        #check multicurrency advance reconcile to ar or ap
        #print "======",advance_aml_dict
        if self.type in ('out_invoice', 'out_refund'):
            amount_diff = debit-debit_adv
        else:
            amount_diff = credit-credit_adv
        #print ("==amount_diff==",amount_diff)
        if (amount_diff) != 0:
            vals_diff = {
                'name': _('Currency exchange rate difference'),
                'debit': amount_diff > 0 and amount_diff or 0.0,
                'credit': amount_diff < 0 and -amount_diff or 0.0,
                'account_id': amount_diff > 0 and adv_line.company_id.currency_exchange_journal_id.default_debit_account_id.id or adv_line.company_id.currency_exchange_journal_id.default_credit_account_id.id,
                'move_id': dst_move.id,
                'currency_id': False,
                'amount_currency': 0,
                'partner_id': adv_line.invoice_id and adv_line.invoice_id.partner_id.id,
            }
            aml_obj.create(vals_diff)
        
        receivable_aml_dict = self._get_shared_move_line_vals(credit, debit, 0, dst_move.id)
        receivable_aml_dict.update({
            'name': _('%s:%s:%s') % (ninv,self.move_id.name, get_name),
            'account_id': cacc,
            'journal_id': adv_line.journal_id and adv_line.journal_id.id or adv_line.invoice_id.journal_id and adv_line.invoice_id.journal_id.id,
            })
        if self.currency_id != self.company_id.currency_id:
            receivable_aml_dict.update({
                'currency_id': self.currency_id.id,
                'amount_currency': credit > 0 and adv_line.base or -adv_line.base,
            })
        #print ("==receivable_aml_dict==",receivable_aml_dict)
        receivable_aml = aml_obj.create(receivable_aml_dict)
        dst_move.post()
        adv_line.write({'move_id': dst_move.id})
        return advance_aml, receivable_aml
    
    @api.multi
    def action_cancel(self):
        moves = self.env['account.move']
        for inv in self:
            if inv.move_id:
                moves += inv.move_id
            if inv.payment_move_line_ids:
                raise UserError(_('You cannot cancel an invoice which is partially paid. You need to unreconcile related payment entries first.'))
            #===================================================================
            #   GET MOVE REGISTERED ADVANCE
            #===================================================================
            if inv.advance_line_ids:
                for adv in inv.advance_line_ids:
                    moves += adv.move_id
            #===================================================================
                
        # First, set the invoices as cancelled and detach the move ids
        self.write({'state': 'cancel', 'move_id': False, 'advance_registered': False})
        if moves:
            # second, invalidate the move(s)
            moves.button_cancel()
            # delete the move this invoice was pointing to
            # Note that the corresponding move_lines and move_reconciles
            # will be automatically deleted too
            moves.unlink()
        #self._log_event(-1.0, 'Cancel Invoice')
        return True
    
    def _prepare_advance_line_ids(self, line):
        if line.currency_id and line.currency_id == self.currency_id:
            amount_to_show = abs(line.amount_residual_currency)
        else:
            amount_to_show = line.company_id.currency_id.with_context(partner_id=self.partner_id.id, date=line.date).compute(abs(line.amount_residual), self.currency_id)
        inv_type = self._context.get('type', 'out_invoice')
        inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [
            ('type', 'in', [TYPE2JOURNALADV[ty] for ty in inv_types if ty in TYPE2JOURNALADV]),
            ('company_id', '=', company_id),
        ]
        journal_id = self.env['account.journal'].search(domain, limit=1)
        #print "====journal_id====",journal_id
        data = {
            'move_line_id': line.id,
            'invoice_id': self.id,
            'type': self.type,
            'journal_id': journal_id and journal_id.id or False,
            'name': line.ref or line.move_id.name,
            'account_id': line.account_id.id,
            'amount': abs(line.debit - line.credit),
            'base': amount_to_show,
        }
        #print "===domain===",data
        return data
    
    def partner_advance_change(self, advance_account_id):
        if not self.partner_id:
            return False
        #print "===partner_id===",self.partner_id
        advance_lines = self.env['account.advance.line']
        posted_advance_line_ids = self.advance_line_ids.filtered(lambda x: x.move_posted_check)
        unposted_advance_line_ids = self.advance_line_ids.filtered(lambda x: not x.move_posted_check)

        # Remove old unposted advance lines. We cannot use unlink() with One2many field
        commands = [(2, line_id.id, False) for line_id in unposted_advance_line_ids]
        
        domain = [('partner_id', '=', self.env['res.partner']._find_accounting_partner(self.partner_id).id), ('reconciled', '=', False), ('amount_residual', '!=', 0.0)]
        if self.type in ('out_invoice', 'in_refund'):
            if not advance_account_id:
                raise UserError(_('You must set Account Advance customer for this partner'))
            self.account_advance_id = advance_account_id.id
            domain.extend([('account_id','=',self.account_advance_id.id),('credit', '>', 0), ('debit', '=', 0)])
        else:
            if not advance_account_id:
                raise UserError(_('You must set Account Advance vendor for this partner'))
            self.account_advance_id = advance_account_id.id
            domain.extend([('account_id','=',self.account_advance_id.id),('credit', '=', 0), ('debit', '>', 0)])
        
        lines = self.env['account.move.line'].search(domain)
        #print ('===partner_advance_change==',lines)
        for line in lines:
            # Load a PO line only once
            data = self._prepare_advance_line_ids(line)
            commands.append((0, False, data))
        #print "==partner_advance_change===",self,advance_account_id
        return self.write({'advance_line_ids': commands})
    
class AccountAdvance(models.Model):
    _name = 'account.advance.line'
    _description = 'Account Advance / Deposit'
    
    invoice_id = fields.Many2one('account.invoice', string='Invoice')
    parent_state = fields.Selection(related='invoice_id.state', string='State of Invoice')
    name = fields.Char(string='Reference', required=True)
    move_line_id = fields.Many2one('account.move.line', string='Move Line Advance', ondelete='cascade')
    account_id = fields.Many2one('account.account', string='Account', required=True)
    company_id = fields.Many2one('res.company', string='Company', related='account_id.company_id', store=True, readonly=True)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True,
        help='Utility field to express amount currency')
    currency_id = fields.Many2one('res.currency', related='move_line_id.currency_id', store=True, readonly=True)
    invoice_currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', store=True, readonly=True)
    amount = fields.Monetary(string='Base')
    base = fields.Monetary(string='Allocate')#, compute='_compute_advance_amount')
    type = fields.Selection([
            ('out_invoice','Customer Invoice'),
            ('in_invoice','Vendor Bill'),
            ('out_refund','Customer Refund'),
            ('in_refund','Vendor Refund'),
        ], readonly=True, index=True, change_default=True,
        default=lambda self: self._context.get('type', 'out_invoice'),
        track_visibility='always')
    journal_id = fields.Many2one('account.journal', string='Journal')
    move_id = fields.Many2one('account.move', 'Advance Entry')
    move_check = fields.Boolean(string='To Linked')
    move_posted_check = fields.Boolean(compute='_get_move_posted_check', string='Posted', track_visibility='always', store=True)

    def create_exchange_rate_entry(self, amount_diff, diff_in_currency, currency, move_date):
        """ Automatically create a journal entry to book the exchange rate difference.
            That new journal entry is made in the company `currency_exchange_journal_id` and one of its journal
            items is matched with the other lines to balance the full reconciliation.
        """
        for rec in self:
            if not rec.company_id.currency_exchange_journal_id:
                raise UserError(_("You should configure the 'Exchange Rate Journal' in the accounting settings, to manage automatically the booking of accounting entries related to differences between exchange rates."))
            if not rec.company_id.income_currency_exchange_account_id.id:
                raise UserError(_("You should configure the 'Gain Exchange Rate Account' in the accounting settings, to manage automatically the booking of accounting entries related to differences between exchange rates."))
            if not rec.company_id.expense_currency_exchange_account_id.id:
                raise UserError(_("You should configure the 'Loss Exchange Rate Account' in the accounting settings, to manage automatically the booking of accounting entries related to differences between exchange rates."))
            move_vals = {'journal_id': rec.company_id.currency_exchange_journal_id.id}

            # The move date should be the maximum date between payment and invoice (in case
            # of payment in advance). However, we should make sure the move date is not
            # recorded after the end of year closing.
            if move_date > rec.company_id.fiscalyear_lock_date:
                move_vals['date'] = move_date
            move = rec.env['account.move'].create(move_vals)
            amount_diff = rec.company_id.currency_id.round(amount_diff)
            diff_in_currency = currency.round(diff_in_currency)
            line_to_reconcile = rec.env['account.move.line'].with_context(check_move_validity=False).create({
                'name': _('Currency exchange rate difference'),
                'debit': amount_diff < 0 and -amount_diff or 0.0,
                'credit': amount_diff > 0 and amount_diff or 0.0,
                'account_id': rec.debit_move_id.account_id.id,
                'move_id': move.id,
                'currency_id': currency.id,
                'amount_currency': -diff_in_currency,
                'partner_id': rec.debit_move_id.partner_id.id,
            })
            rec.env['account.move.line'].create({
                'name': _('Currency exchange rate difference'),
                'debit': amount_diff > 0 and amount_diff or 0.0,
                'credit': amount_diff < 0 and -amount_diff or 0.0,
                'account_id': amount_diff > 0 and rec.company_id.currency_exchange_journal_id.default_debit_account_id.id or rec.company_id.currency_exchange_journal_id.default_credit_account_id.id,
                'move_id': move.id,
                'currency_id': currency.id,
                'amount_currency': diff_in_currency,
                'partner_id': rec.debit_move_id.partner_id.id,
            })
#             for aml in aml_to_fix:
#                 partial_rec = rec.env['account.partial.reconcile'].create({
#                     'debit_move_id': aml.credit and line_to_reconcile.id or aml.id,
#                     'credit_move_id': aml.debit and line_to_reconcile.id or aml.id,
#                     'amount': abs(aml.amount_residual),
#                     'amount_currency': abs(aml.amount_residual_currency),
#                     'currency_id': currency.id,
#                 })
            move.post()
        return line_to_reconcile#, partial_rec

    @api.onchange('move_check')
    def _onchange_move_check(self):
        if self.base > self.invoice_id.amount_total:
            self.move_check = False
    
    @api.multi
    @api.depends('move_id.state')
    def _get_move_posted_check(self):
        for line in self:
            line.move_posted_check = True if line.move_id and line.move_id.state == 'posted' else False
    
    @api.multi
    def action_apply(self):
        invoice_obj = self.env['account.invoice'].browse(self.invoice_id.id)
        ar_account_ids = self.invoice_id.move_id.line_ids.filtered(lambda r: r.account_id == self.account_id)
        for adv_line in self:
            if adv_line.move_check:
                #line.write({'move_check': False})
                adv_account_ids = adv_line.move_line_id                    
                advance_aml_ids = invoice_obj._create_advance_entry(adv_line)
                adv_to_reconcile = adv_account_ids+advance_aml_ids[0]
                adv_to_reconcile.reconcile()
                ar_account_ids += advance_aml_ids[1]
        if ar_account_ids:
            ar_account_ids.reconcile()
        return