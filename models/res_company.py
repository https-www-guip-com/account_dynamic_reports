# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    strict_range = fields.Boolean(string='Use Strict Range', default=True,
                                  help='Use this if you want to show TB with retained earnings section')
    bucket_1 = fields.Integer(string='Bucket 1', required=True, default=30)
    bucket_2 = fields.Integer(string='Bucket 2', required=True, default=60)
    bucket_3 = fields.Integer(string='Bucket 3', required=True, default=90)
    bucket_4 = fields.Integer(string='Bucket 4', required=True, default=120)
    bucket_5 = fields.Integer(string='Bucket 5', required=True, default=180)
    date_range = fields.Selection(
        [('today', 'Hoy'),
         ('this_week', 'Esta semana'),
         ('this_month', 'Este Mes'),
         ('this_quarter', 'Este cuarto'),
         ('this_financial_year', 'Este año financiero'),
         ('yesterday', 'Ayer'),
         ('last_week', 'La Semana Pasado'),
         ('last_month', 'El Mes Pasado'),
         ('last_quarter', 'Último cuarto'),
         ('last_financial_year', 'Último año financiero')],
        string='Intervalo de fechas predeterminado', default='this_financial_year', required=True
    )
    financial_year = fields.Selection([
        ('april_march','1 April to 31 March'),
        ('july_june','1 july to 30 June'),
        ('january_december','1 Jan to 31 Dec')
        ], string='Año financiero', default='january_december', required=True)


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    excel_format = fields.Char(string='Excel Formato', default='_ * #,##0.00_) ;_ * - #,##0.00_) ;_ * "-"??_) ;_ @_ ', required=True)

class ins_account_financial_report(models.Model):
    _name = "ins.account.financial.report"
    _description = "Account Report"

    @api.depends('parent_id', 'parent_id.level')
    def _get_level(self):
        '''Returns a dictionary with key=the ID of a record and value = the level of this
           record in the tree structure.'''
        for report in self:
            level = 0
            if report.parent_id:
                level = report.parent_id.level + 1
            report.level = level

    def _get_children_by_order(self, strict_range):
        '''returns a recordset of all the children computed recursively, and sorted by sequence. Ready for the printing'''
        res = self
        children = self.search([('parent_id', 'in', self.ids)], order='sequence ASC')
        if children:
            for child in children:
                res += child._get_children_by_order(strict_range)
        if not strict_range:
            res -= self.env.ref('account_dynamic_reports.ins_account_financial_report_unallocated_earnings0')
            res -= self.env.ref('account_dynamic_reports.ins_account_financial_report_equitysum0')
        return res

    name = fields.Char('Nombre Reporte', required=True, translate=True)
    parent_id = fields.Many2one('ins.account.financial.report', 'Padre')
    children_ids = fields.One2many('ins.account.financial.report', 'parent_id', 'Informe de cuentas')
    sequence = fields.Integer('Sequencia')
    level = fields.Integer(compute='_get_level', string='Nivel', store=True)
    type = fields.Selection([
        ('sum', 'Vistas'),
        ('accounts', 'Cuentas'),
        ('account_type', 'Tipo de cuentas'),
        ('account_report', 'Valor del informe'),
        ], 'Type', default='sum')
    account_ids = fields.Many2many('account.account', 'ins_account_account_financial_report', 'report_line_id', 'account_id', 'Cuentas')
    account_report_id = fields.Many2one('ins.account.financial.report', 'Valor Del Informe')
    account_type_ids = fields.Many2many('account.account.type', 'ins_account_account_financial_report_type', 'report_id', 'account_type_id', 'Tipo de Cuentas')
    sign = fields.Selection([('-1', 'Signo de equilibrio inverso'), ('1', 'Conservar el signo de equilibrio')], 'Iniciar sesión en informes', required=True, default='1',
                            help='For accounts that are typically more debited than credited and that you would like to print as negative amounts in your reports, you should reverse the sign of the balance; e.g.: Expense account. The same applies for accounts that are typically more credited than debited and that you would like to print as positive amounts in your reports; e.g.: Income account.')
    range_selection = fields.Selection([
        ('from_the_beginning', 'Desde el principio'),
        ('current_date_range', 'Basado en el rango de fechas actual'),
        ('initial_date_range', 'Basado en el intervalo de fechas inicial')],
        help='"From the beginning" will select all the entries before and on the date range selected.'
             '"Based on Current Date Range" will select all the entries strictly on the date range selected'
             '"Based on Initial Date Range" will select only the initial balance for the selected date range',
        string='Intervalo de fechas personalizado')
    display_detail = fields.Selection([
        ('no_detail', 'Sin detalle'),
        ('detail_flat', 'Display children flat'),
        ('detail_with_hierarchy', 'Mostrar hijos con jerarquía')
        ], 'Mostrar detalles', default='detail_flat')
    style_overwrite = fields.Selection([
        ('0', 'Formateo automático'),
        ('1', 'Título principal 1 (bold, underlined)'),
        ('2', 'Título 2 (bold)'),
        ('3', 'Título 3 (bold, smaller)'),
        ('4', 'Texto Normal'),
        ('5', 'Texto Italico (smaller)'),
        ('6', 'Texto Pequeños '),
        ], 'Estilo de informe financiero', default='0',
        help="You can set up here the format you want this record to be displayed. If you leave the automatic formatting, it will be computed based on the financial reports hierarchy (auto-computed field 'level').")


class AccountAccount(models.Model):
    _inherit = 'account.account'

    def get_cashflow_domain(self):
        cash_flow_id = self.env.ref('account_dynamic_reports.ins_account_financial_report_cash_flow0')
        if cash_flow_id:
            return [('parent_id.id', '=', cash_flow_id.id)]

    cash_flow_category = fields.Many2one('ins.account.financial.report', string="Cash Flow type", domain=get_cashflow_domain)

    @api.onchange('cash_flow_category')
    def onchange_cash_flow_category(self):
        # Add account to cash flow record to account_ids
        if self._origin and self._origin.id:
            self.cash_flow_category.write({'account_ids': [(4, self._origin.id)]})
            self.env.ref(
                'account_dynamic_reports.ins_account_financial_report_cash_flow0').write(
                {'account_ids': [(4, self._origin.id)]})
        # Remove account from previous category
        # In case of changing/ removing category
        if self._origin.cash_flow_category:
            self._origin.cash_flow_category.write({'account_ids': [(3, self._origin.id)]})
            self.env.ref(
                'account_dynamic_reports.ins_account_financial_report_cash_flow0').write(
                {'account_ids': [(3, self._origin.id)]})
