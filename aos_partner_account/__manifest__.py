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
    'name': 'Partner Account',
    'version': '12.0.0.1.0',
    'author': "Alphasoft",
    'sequence': 1,
    'website': 'https://www.alphasoft.co.id/',
    'license': 'AGPL-3',
    'category': 'Accounting',
    'summary': 'Advance of a module by Alphasoft',
    'images':  ['images/main_screenshot.png'],
    'depends': ['account'],
    'description': """
Module based on Alphasoft
=====================================================
* Add fields Account Advance Receivable & Advance Payable on partner
* Additional Info for Customer
""",
    'demo': [],
    'test': [],
    'data': [
        'views/res_partner_view.xml',
     ],
    'css': [],
    'js': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
