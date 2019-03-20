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
from odoo.exceptions import UserError


class HrScheduleGenerate(models.TransientModel):
    _name = 'hr.schedule.generate'
    _description = 'Generate Schedules'

    date_start = fields.Date(
        string='Start', required=True
    )
    no_weeks = fields.Integer(
        string='Number of weeks', required=True, default=2
    )
    employee_ids = fields.Many2many(
        comodel_name='hr.employee', relation='hr_employee_schedule_rel',
        column1='generate_id', column2='employee_id', string='Employees'
    )

    @api.multi
    @api.onchange('date_start')
    def onchange_start_date(self):
        if self.date_start:
            date_start = datetime.strptime(self.date_start, '%Y-%m-%d').date()
            # The schedule must start on a Monday
            if date_start.weekday() == 0:
                self.date_start = date_start.strftime('%Y-%m-%d')
            else:
                raise UserError(
                    _("The start date of the schedule must start on mondays"))

    @api.multi
    def generate_schedules(self):
        # TODO Este código para el wizard no está preparado para afrontar más
        # de un objeto. Posiblemente haga falta corregirlo.
        self.ensure_one()
        schedule_obj = self.env['hr.schedule']
        employee_obj = self.env['hr.employee']

        date_start = datetime.strptime(self.date_start, '%Y-%m-%d').date()
        date_end = date_start + relativedelta(weeks=+self.no_weeks, days=-1)
        schedules = self.env['hr.schedule']

        if len(self.employee_ids) > 0:
            for employee in self.employee_ids:
                if (not employee.contract_id
                        or not employee.contract_id.schedule_template_id):
                    continue

                schedule_vals = {
                    'name': (employee.name + ': ' + self.date_start + ' Wk ' +
                             str(date_start.isocalendar()[1])),
                    'employee_id': employee.id,
                    'template_id': employee.contract_id.schedule_template_id.id,
                    'date_start': date_start.strftime('%Y-%m-%d'),
                    'date_end': date_end.strftime('%Y-%m-%d'),
                }

                schedules = schedules + \
                    schedule_obj.create(schedule_vals)

        return {
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'hr.schedule',
            'domain': [('id', 'in', schedules.ids)],
            'type': 'ir.actions.act_window',
            'target': 'current'
        }
