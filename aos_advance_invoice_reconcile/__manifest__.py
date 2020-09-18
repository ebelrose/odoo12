# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    This module copyright (C) 2017 Alphasoft
#    (<http://www.adeanshori.co.id>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': 'Down Payment to Reconcile',
    'version': '12.0.0.1.0',
    'author': "Alphasoft",
    'sequence': 1,
    'website': 'https://www.alphasoft.co.id/',
    'license': 'AGPL-3',
    'category': 'Accounting',
    'summary': 'Advance & Invoice Reconcile',
    'depends': ['account', 'aos_base_account', 'aos_partner_account'],
    'images':  ['images/main_screenshot.png'],
    'description': """
Module based on Alphasoft
=====================================================
* Menu Down payment (Sales and Purchases)
* Allow to create advance payment (Downpayment)
* Accrue from Invoice
* Allow to reconciled with related invoice
* Allow to reconciled partial down payment to invoice
* Manage multi currency, make gain loss for difference date
""",
    'demo': [],
    'test': [],
    'data': [
        "security/ir.model.access.csv",
        'wizard/update_advance_view.xml',
        'views/product_view.xml',
        'views/partner_view.xml',
        'views/account_invoice_view.xml',
     ],
    'css': [],
    'js': [],
    'price': 85.00,
    'currency': 'EUR',
    'installable': True,
    'application': False,
    'auto_install': False,
}
