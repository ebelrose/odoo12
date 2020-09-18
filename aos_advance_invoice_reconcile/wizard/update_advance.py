from odoo import api, fields, models, _
from odoo.exceptions import UserError

class UpdateAdvancePayment(models.TransientModel):
    _name = "update.advance.payment"
    _description = "Update Advance Payment"
    
    account_id = fields.Many2one('account.account', string='Advance Account', required=True)
    
    @api.model
    def default_get(self, fields):
        context = self._context or {}
        res = super(UpdateAdvancePayment, self).default_get(fields)
        invoices = self.env['account.invoice'].browse(context.get('active_ids', []))
        for inv in invoices:
            if 'account_id' in fields:
                res.update({'account_id': inv.account_advance_id and inv.account_advance_id.id or False})
        return res
    
    @api.multi
    def action_update(self):
        context = dict(self._context or {})
        invoices = self.env['account.invoice'].browse(context.get('active_ids'))
        for advance in self:
            for invoice in invoices:
                invoice.partner_advance_change(advance.account_id)
        return {'type': 'ir.actions.act_window_close'}
