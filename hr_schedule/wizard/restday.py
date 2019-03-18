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

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pytz import timezone, utc

from odoo import fields, api, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import UserError
from odoo import _


class HrRestdayWizard(models.TransientModel):
    _name = 'hr.restday.wizard'
    _description = 'Schedule Template Change Wizard'

    employee_id = fields.Many2one(
        comodel_name='hr.employee', string='Employee', required=True
    )
    contract_id = fields.Related(
        comodel_name="hr.contract", string="Contract",
        related='employee_id.contract_id', readonly=True
    )
    st_current_id = fields.Many2one(
        comodel_name='hr.schedule.template', string='Current Template',
        readonly=True
    )
    st_new_id = fields.Many2one(
        comodel_name='hr.schedule.template', string='New Template'
    )
    permanent = fields.Boolean(
        string='Make Permanent'
    )
    temp_restday = fields.Boolean(
        string='Temporary Rest Day Change',
        help="If selected, change the rest day to the specified day only "
             "for the selected schedule.",
        default=False
    )
    dayofweek = fields.Selection(
        selection=[
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday')
        ], string='Rest Day', select=True
    )
    temp_week_start = fields.Date(
        string='Start of Week'
    )
    week_start = fields.Date(
        string='Start of Week'
    )

    @api.multi
    @api.onchange('employee_id')
    def onchange_employee(self):
        if self.employee_id:
            self.st_current_id = self.employee_id.contract_id.\
                schedule_template_id.id

    @api.multi
    @api.onchange('week_start')
    def onchange_week(self):
        if self.week_start:
            date = datetime.strptime(self.week_start, "%Y-%m-%d")
            if date.weekday() != 0:
                self.week_start = False
            else:
                raise UserError(
                    _("The starting week of the restday must start on mondays")
                )

    @api.multi
    @api.onchange('temp_week_start')
    def onchange_temp_week(self):
        if self.temp_week_start:
            date = datetime.strptime(self.temp_week_start, "%Y-%m-%d")
            if date.weekday() != 0:
                self.temp_week_start = False
            else:
                raise UserError(
                    _("The temporal start date of the restday must start"
                      " on mondays")
                )

    @api.model
    def _create_detail(self, schedule, actual_dayofweek,
                       template_dayofweek, week_start):
        # First, see if there's a schedule for the actual dayofweek.
        # If so, use it.
        #
        for worktime in schedule.template_id.worktime_ids:
            if worktime.dayofweek == actual_dayofweek:
                template_dayofweek = actual_dayofweek

        prev_utc_dt_start = False
        prev_day_of_week = False
        local_tz = self.env.user.tz
        date_scheduled_start = datetime.strptime(
            schedule.date_start, DEFAULT_SERVER_DATE_FORMAT
        ).date()
        date_week_start = schedule.date_start < week_start and\
                          datetime.strptime(week_start,
                                            DEFAULT_SERVER_DATE_FORMAT
                                            ).date() or date_scheduled_start

        for worktime in schedule.template_id.worktime_ids:
            if worktime.dayofweek != template_dayofweek:
                continue

            from_hour, from_separator, from_minute = \
                worktime.hour_from.partition(':')
            to_hour, to_separator, to_minute = worktime.hour_to.partition(':')

            if len(from_separator) == 0 or len(to_separator) == 0:
                raise UserError(
                    _('The time should be entered as HH:MM')
                )

            # TODO - Someone affected by DST should fix this
            #
            dt_start = datetime.strptime(
                date_week_start.strftime('%Y-%m-%d') + ' ' + from_hour + ':'
                + from_minute + ':00', '%Y-%m-%d %H:%M:%S'
            )
            local_dt_start = local_tz.localize(dt_start, is_dst=False)
            utc_dt_start = local_dt_start.astimezone(utc)

            if actual_dayofweek != '0':
                utc_dt_start = utc_dt_start + \
                    relativedelta(days=+int(actual_dayofweek))

            date_day = utc_dt_start.astimezone(local_tz).date()

            # If this worktime is a continuation (i.e - after lunch) set the
            # start time based on the difference from the previous record
            #
            if prev_day_of_week and prev_day_of_week == actual_dayofweek:
                prev_hour = prev_utc_dt_start.strftime('%H')
                prev_minute = prev_utc_dt_start.strftime('%M')
                current_hour = utc_dt_start.strftime('%H')
                current_minute = utc_dt_start.strftime('%M')
                delta_seconds = (
                    datetime.strptime(
                        current_hour + ':' + current_minute, '%H:%M'
                    ) -
                    datetime.strptime(
                        prev_hour + ':' + prev_minute, '%H:%M'
                    )
                ).seconds
                utc_dt_start = prev_utc_dt_start + \
                               timedelta(seconds=+delta_seconds)
                date_day = prev_utc_dt_start.astimezone(local_tz).date()

            delta_seconds = (
                datetime.strptime(to_hour + ':' + to_minute, '%H:%M') -
                datetime.strptime(from_hour + ':' + from_minute, '%H:%M')
            ).seconds
            utc_dt_end = utc_dt_start + timedelta(seconds=+delta_seconds)

            val = {
                'name': schedule.name,
                'dayofweek': actual_dayofweek,
                'day': date_day,
                'date_start': utc_dt_start.strftime('%Y-%m-%d %H:%M:%S'),
                'date_end': utc_dt_end.strftime('%Y-%m-%d %H:%M:%S'),
                'schedule_id': schedule.id,
            }

            schedule.write({
                'detail_ids': [(0, 0, val)]
            })

            prev_day_of_week = worktime.dayofweek
            prev_utc_dt_start = utc_dt_start

    @api.model
    def _change_restday(self, employee_id, week_start, dayofweek):
        schedule_obj = self.pool.get('hr.schedule')
        schedule_detail_obj = self.pool.get('hr.schedule.detail')

        schedule_ids = schedule_obj.search([
            ('employee_id', '=', employee_id),
            ('date_start', '<=', week_start),
            ('date_end', '>=', week_start),
            ('state', 'not in', ['locked'])
        ])
        schedule = schedule_obj.browse(schedule_ids[0])
        dt_first_day = datetime.strptime(
            schedule.detail_ids[0].date_start, DEFAULT_SERVER_DATETIME_FORMAT)
        date_start = (
            dt_first_day.strftime(DEFAULT_SERVER_DATE_FORMAT) < week_start
            and week_start + ' ' + dt_first_day.strftime('%H:%M:%S')
            or dt_first_day.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        )
        dt_next_week = datetime.strptime(
            date_start, DEFAULT_SERVER_DATETIME_FORMAT
        ) + relativedelta(weeks=+1)

        # First get the current rest days
        rest_days = schedule.get_rest_days_by_id(
            dt_first_day.strftime(DEFAULT_SERVER_DATE_FORMAT)
        ) # sched.get_rest_days_by_id(dtFirstDay.strftime(OE_DFORMAT)

        # Next, remove the schedule detail for the new rest day
        for detail in schedule.detail_ids:
            if (detail.date_start < week_start
                    or datetime.strptime(detail.date_start,
                                         DEFAULT_SERVER_DATETIME_FORMAT)
                    >= dt_next_week):
                continue
            if detail.dayofweek == dayofweek:
                detail.unlink()

        # Enter the new rest day(s)
        #
        schedule_obj = self.pool.get('hr.schedule')
        nrest_days = [dayofweek] + rest_days[1:]
        date_schedule_start = datetime.strptime(
            schedule.date_start,DEFAULT_SERVER_DATE_FORMAT
        ).date()
        date_week_start = schedule.date_start < week_start and \
                          datetime.strptime(week_start,
                                            DEFAULT_SERVER_DATE_FORMAT
                                            ).date() or date_schedule_start
        week_delta = relativedelta(days=+7)

        if date_week_start == date_schedule_start:
            schedule.add_restdays('restday_ids1', rest_days=nrest_days)
        elif date_week_start == date_schedule_start + week_delta:
            schedule.add_restdays('restday_ids2', rest_days=nrest_days)
        elif date_week_start == date_schedule_start + week_delta * 2:
            schedule.add_restdays('restday_ids3', rest_days=nrest_days)
        elif date_week_start == date_schedule_start + week_delta * 3:
            schedule.add_restdays('restday_ids4', rest_days=nrest_days)
        elif date_week_start == date_schedule_start + week_delta * 4:
            schedule.add_restdays('restday_ids5', rest_days=nrest_days)

        # Last, add a schedule detail for the first rest day in the week using
        # the template for the new (temp) rest day
        #
        if len(rest_days) > 0:
            schedule._create_detail(str(rest_days[0]), dayofweek, week_start)

    @api.multi
    def _remove_add_schedule(self, schedules, week_start, tpl_id):
        """
        Remove the current schedule and add a new one in its place
        according to the new template. If the week that the change
        starts in is not at the beginning of a schedule create two
        new schedules to accommodate the truncated old one and the
        partial new one.
        """
        schedule_obj = self.env['hr.schedule']
        for schedule in schedules:
            vals2 = False
            vals1 = {
                'name': schedule.name,
                'employee_id': schedule.employee_id.id,
                'template_id': tpl_id,
                'date_start': schedule.date_start,
                'date_end': schedule.date_end,
            }

            if week_start > schedule.date_start:
                date_week_start = datetime.strptime(
                    week_start, '%Y-%m-%d'
                ).date()
                start_day = date_week_start.strftime('%Y-%m-%d')
                vals1['template_id'] = schedule.template_id.id
                vals1['date_end'] = (
                    date_week_start + relativedelta(days=-1)
                ).strftime('%Y-%m-%d')
                vals2 = {
                    'name': (schedule.employee_id.name + ': ' + start_day +
                             ' Wk ' + str(date_week_start.isocalendar()[1])),
                    'employee_id': schedule.employee_id.id,
                    'template_id': tpl_id,
                    'date_start': start_day,
                    'date_end': schedule.date_end,
                }

            schedule.unlink()
            schedule_obj.create(vals1)
            if vals2:
                schedule_obj.create(vals2)

    def _change_by_template(self, employee_id, week_start, new_template_id,
                            doall):
        sched_obj = self.env['hr.schedule']

        schedule_ids = sched_obj.search([
            ('employee_id', '=', employee_id),
            ('date_start', '<=', week_start),
            ('date_end', '>=', week_start),
            ('state', 'not in', ['locked'])
        ])

        # Remove the current schedule and add a new one in its place according
        # to the new template
        #
        if len(schedule_ids) > 0:
            self._remove_add_schedule(schedule_ids[0], week_start,
                                      new_template_id)

        # Also, change all subsequent schedules if so directed
        if doall:
            schedules = sched_obj.search([
                ('employee_id', '=', employee_id),
                ('date_start', '>', week_start),
                ('state', 'not in', ['locked'])
            ])

            self._remove_add_schedule(schedules, week_start, new_template_id)

    def change_restday(self):
        # Change the rest day for only one schedule
        if self.temp_restday and \
                self.dayofweek and \
                self.temp_week_start:
            self._change_restday(
                self.employee_id, self.temp_week_start, self.dayofweek
            )

        # Change entire week's schedule to the chosen schedule template
        if not self.temp_restday and \
                self.st_new_id and \
                self.week_start:
            if self.week_start:
                self._change_by_template(
                    self.employee_id, self.week_start or False,
                    self.st_new_id or False, self.permanent or False)

            # If this change is permanent modify employee's contract to
            # reflect the new template
            #
            if self.permanent:
                self.contract_id.write({
                    'schedule_template_id': self.st_new_id,
                })

        return {
            'name': 'Change Schedule Template',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'hr.restday.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
