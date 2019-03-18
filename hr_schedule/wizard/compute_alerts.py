# -*- coding:utf-8 -*-
#
#
#    Copyright (C) 2013 Michael Telahun Makonnen <mmakonnen@gmail.com>.
#    All Rights Reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import fields, api, models


class WizardComputeAlerts(models.TransientModel):
    _name = 'hr.schedule.alert.compute'
    _description = 'Check Alerts'

    date_start = fields.Date(
        string='Start', required=True
    )
    date_end = fields.Date(
        string='End', required=True
    )
    employee_ids = fields.Many2many(
        comodel_name='hr.employee', relation='hr_employee_alert_rel',
        column1='generate_id', column2='employee_id', string='Employees'
    )

    @api.multi
    def generate_alerts(self):
        # TODO Este código para el wizard no está preparado para afrontar más
        # de un objeto. Posiblemente haga falta corregirlo.
        self.ensure_one()
        alert_obj = self.env['hr.schedule.alert']

        date_start = datetime.strptime(self.date_start, '%Y-%m-%d').date()
        date_end = datetime.strptime(self.date_end, '%Y-%m-%d').date()
        date_today = datetime.strptime(fields.Date.context_today(), '%Y-%m-%d')\
            .date()

        if date_today < date_end:
            date_end = date_today

        date_next = date_start
        for employee in self.employee_ids:
            while date_next <= date_end:
                alert_obj.compute_alerts_by_employee(
                    employee, date_next.strftime('%Y-%m-%d')
                )

                date_next += relativedelta(days=+1)

        return {
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'hr.schedule.alert',
            'domain': [
                ('employee_id', 'in', self.employee_ids.ids),
                '&',
                ('name', '>=', self.date_start + ' 00:00:00'),
                ('name', '<=', self.date_end + ' 23:59:59')
            ],
            'type': 'ir.actions.act_window',
            'target': 'current',
            'nodestroy': True,
        }
