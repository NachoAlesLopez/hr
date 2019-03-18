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
from odoo import fields, api, models
from odoo.workflow import trg_validate


class DepartmentSelection(models.TransientModel):
    _name = 'hr.schedule.validate.departments'
    _description = 'Department Selection for Validation'

    department_ids = fields.Many2many(
        comodel_name='hr.department',
        relation='hr_department_group_rel',
        column1='employee_id',
        column2='department_id',
        string='Departments'
    )

    @api.multi
    def view_schedules(self):
        return {
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'hr.schedule',
            'domain': [
                ('department_id', 'in', self.department_ids.ids),
                ('state', 'in', ['draft']),
            ],
            'type': 'ir.actions.act_window',
            'target': 'new'
        }

    @api.multi
    def do_validate(self):
        schedules = self.env['hr.schedule'].search([
            ('department_id', 'in', self.department_ids.ids)
        ])

        for sched_id in schedules:
            trg_validate(self.env.uid, 'hr.schedule', sched_id,
                         'signal_validate', cr)

        return {'type': 'ir.actions.act_window_close'}
