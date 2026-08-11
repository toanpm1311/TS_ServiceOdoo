# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.tools.safe_eval import safe_eval
from dateutil.relativedelta import relativedelta
from pytz import timezone
import pytz
import logging
_logger = logging.getLogger(__name__)

def get_query(self, args, model_name, operation, field, start_date=None, end_date=None,
              group_by=False, apply_ir_rules=False):
    """ Dashboard block Query Creation """
    query = self._where_calc(args)
    if apply_ir_rules:
        self._apply_ir_rules(query, 'read')
    if operation and field:
        data = 'COALESCE(%s("%s".%s),0) AS value' % (
            operation.upper(), self._table, field.name)
        join = ''
        group_by_str = ''
        if group_by:
            if group_by.ttype == 'many2many':
                group_by_name = group_by.name
                # Lấy thông tin M2M
                field_info = self.env[model_name]._fields[group_by_name]
                m2m_table = field_info.relation
                m2m_col_model = field_info.column1
                m2m_col_relation = field_info.column2
                # JOIN
                join = ' INNER JOIN "%s" ON "%s".%s = "%s".id' % (
                        m2m_table, m2m_table, m2m_col_model,self._table)
                # SELECT
                data += ', %s.%s AS %s' % (m2m_table, m2m_col_relation,group_by_name)
                # GROUP BY
                group_by_str = ' GROUP BY %s.%s' % (m2m_table,m2m_col_relation)

            elif group_by.ttype == 'many2one':
                group_by_name = group_by.name
                # JOIN
                join = ("")
                # SELECT
                data += ', "%s".%s AS %s' % (self._table,group_by_name,group_by_name)
                # GROUP BY
                group_by_str = ' GROUP BY %s.%s' % (self._table,group_by_name)

            elif group_by.ttype == 'selection':
                try:
                    selection_list = safe_eval(group_by.selection)
                except Exception:
                    selection_list = []

                selection_map = dict(selection_list)

                case_expr = 'CASE "{table}"."{field}"'.format(
                    table=self._table, field=group_by.name
                )
                for key, label in selection_map.items():
                    safe_label = label.replace("'", "''")
                    case_expr += " WHEN '{k}' THEN '{l}'".format(k=key, l=safe_label)
                case_expr += ' ELSE NULL END'

                data += ', {expr} AS {field}'.format(expr=case_expr, field=group_by.name)
                group_by_str = ' GROUP BY {expr}'.format(expr=case_expr)

            else:
                data = data + ',"%s".%s' % (self._table, group_by.name)
                group_by_str = ' Group by "%s".%s' % (
                    self._table, str(group_by.name))
    else:
        data = '"%s".id' % (self._table)
    from_clause, where_clause, where_clause_params = query.get_sql()
    where_str = where_clause and (" WHERE %s" % where_clause) or ''

    def get_company_m2o_fields(model_name):
        model = self.env[model_name]
        return [
            fname
            for fname, field in model._fields.items()
            if field.type == 'many2one'
               and getattr(field, 'comodel_name', False) == 'res.company'
        ]

    allowed_company_ids = self.env.context.get('allowed_company_ids')
    # Add filter for allowed companies if provided
    if allowed_company_ids:
        company_fields = get_company_m2o_fields(model_name)
        if company_fields:
            field_name = 'company_id' if 'company_id' in company_fields else company_fields[0]
            where_str += ' AND "%s".%s IN (%s)' % (
                self._table, field_name, ','.join(map(str, allowed_company_ids))
            )

    user_tz = self.env.user.tz or 'UTC'
    tz = timezone(user_tz)

    if start_date and start_date != 'null':
        if len(start_date) == 10:
            dt_start = fields.Date.from_string(start_date)
            dt_start = fields.Datetime.from_string(f"{dt_start} 00:00:00")
            dt_start_local = tz.localize(dt_start)
            dt_start_utc = dt_start_local.astimezone(pytz.utc)
            start_date = fields.Datetime.to_string(dt_start_utc)
        start_date_query = f' AND ({from_clause}."create_date" >= \'{start_date}\')'
    else:
        start_date_query = ''
    if end_date and end_date != 'null':
        if len(end_date) == 10:
            dt_end = fields.Date.from_string(end_date)
            dt_end = fields.Datetime.from_string(f"{dt_end} 00:00:00")
            dt_end_local = tz.localize(dt_end + relativedelta(days=1, seconds=-1))
            dt_end_utc = dt_end_local.astimezone(pytz.utc)
            end_date = fields.Datetime.to_string(dt_end_utc)
        end_date_query = f' AND ({from_clause}."create_date" <= \'{end_date}\')'
    else:
        end_date_query = ''
    query_str = 'SELECT %s FROM ' % data + from_clause + join + where_str + start_date_query + end_date_query + group_by_str
    def format_param(x):
        if not isinstance(x, tuple):
            return "'" + str(x) + "'"
        elif isinstance(x, tuple) and len(x) == 1:
            return "(" + str(x[0]) + ")"
        else:
            return str(x)

    exact_query = query_str % tuple(map(format_param, where_clause_params))
    return exact_query


models.BaseModel.get_query = get_query
