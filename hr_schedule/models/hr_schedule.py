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

from odoo import fields, api, models, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT,\
    DEFAULT_SERVER_DATE_FORMAT
from odoo.workflow import trg_validate


class HrSchedule(models.Model):
    _name = 'hr.schedule'
    _inherit = ['mail.thread']
    _description = 'Employee Schedule'

    def _compute_alerts(self):
        for schedule in self:
            alert_ids = []
            for detail in schedule.detail_ids:
                [alert_ids.append(a.id) for a in detail.alert_ids]
            schedule.alert_ids = alert_ids

    name = fields.Char(
        string="Description", required=True,
        states={'locked': [('readonly', True)]}
    )

    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', readonly=True,
        default=lambda self:
            self.env['res.company']._company_default_get('hr.schedule'),
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee', string='Employee', required=True,
        states={'locked': [('readonly', True)]}
    )
    template_id = fields.Many2one(
        comodel_name='hr.schedule.template', string='Schedule Template',
        states={'locked': [('readonly', True)]}
    )
    detail_ids = fields.One2many(
        comodel_name='hr.schedule.detail', inverse_name='schedule_id',
        string='Schedule Detail', states={'locked': [('readonly', True)]}
    )
    date_start = fields.Date(
        string='Start Date', required=True,
        states={'locked': [('readonly', True)]}
    )
    date_end = fields.Date(
        string='End Date', required=True
    )
    department_id = fields.Many2one(
        comodel_name='hr.department', string='Department',
        related='employee_id.department_id', readonly=True, store=True
    )
    alert_ids = fields.One2many(
        comodel_name='hr.schedule.alert', string='Alerts',
        compute="_compute_alerts", readonly=True
    )
    restday_ids1 = fields.Many2many(
        comodel_name='hr.schedule.weekday', relation='schedule_restdays_rel1',
        column1='sched_id', column2='weekday_id', string='Rest Days Week 1',
        states={'locked': [('readonly', True)]}
    )
    restday_ids2 = fields.Many2many(
        comodel_name='hr.schedule.weekday', relation='schedule_restdays_rel2',
        column1='sched_id', column2='weekday_id', string='Rest Days Week 2',
        states={'locked': [('readonly', True)]}
    )
    restday_ids3 = fields.Many2many(
        comodel_name='hr.schedule.weekday', relation='schedule_restdays_rel3',
        column1='sched_id', column2='weekday_id', string='Rest Days Week 3',
        states={'locked': [('readonly', True)]}
    )
    restday_ids4 = fields.Many2many(
        comodel_name='hr.schedule.weekday', relation='schedule_restdays_rel4',
        column1='sched_id', column2='weekday_id', string='Rest Days Week 4',
        states={'locked': [('readonly', True)]}
    )
    restday_ids5 = fields.Many2many(
        comodel_name='hr.schedule.weekday', relation='schedule_restdays_rel5',
        column1='sched_id', column2='weekday_id', string='Rest Days Week 5',
        states={'locked': [('readonly', True)]}
    )
    state = fields.Selection(
        selection=[
            ('draft', "Draft"),
            ('confirmed', "Confirmed"),
            ('locked', "Locked")
        ],
        string="State", readonly=True, default='draft'
    )

    @api.model
    def _check_overlapping_schedules(self, values):
        schedules = self.env['hr.schedule'].search([
            ('date_start', '>=', values['date_start']),
            ('date_end', '<=', values['date_end']),
            ('employee_id', '=', values['employee_id'])
        ])

        if schedules:
            raise UserError(_('You cannot have schedules that overlap!'))

    # TODO: Sin usar????
    # @api.multi  # ?
    # def get_rest_days(self, employee_id, dt):
    #     """
    #     If the rest day(s) have been explicitly specified that's
    #     what is returned, otherwise a guess is returned based on the
    #     week days that are not scheduled. If an explicit rest day(s)
    #     has not been specified an empty list is returned. If it is able
    #     to figure out the rest days it will return a list of week day
    #     integers with Monday being 0.
    #     """
    #     day = dt.strftime()
    #     schedule = self.env['hr.schedule'].search([
    #         ('employee_id', '=', employee_id.id),
    #         ('date_start', '<=', day),
    #         ('date_end', '>=', day),
    #     ])
    #
    #     if not schedule:
    #         return None
    #     elif len(schedule) > 1:
    #         raise UserError(
    #             _('Employee has a scheduled date in more than one schedule.')
    #         )
    #
    #     # If the day is in the middle of the week get the start of the week
    #     if dt.weekday() == 0:
    #         week_start = dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    #     else:
    #         week_start = \
    #             (dt + relativedelta(days=-datetime.weekday()))\
    #                 .strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    #
    #     return self.get_rest_days_by_id(week_start)

    @api.multi
    def get_rest_days_by_id(self, week_start):
        """
        If the rest day(s) have been explicitly specified that's
        what is returned, otherwise a guess is returned based on the
        week days that are not scheduled. If an explicit rest day(s)
        has not been specified an empty list is returned. If it is
        able to figure out the rest days it will return a list of week
        day integers with Monday being 0.
        """
        res = []

        # Set the boundaries of the week (i.e- start of current week and start
        # of next week)
        for schedule in self:
            if not schedule.detail_ids:
                return res

            first_detail_start = schedule.detail_ids[0].date_start

            dt_first_day = \
                datetime.strptime(first_detail_start,
                                  DEFAULT_SERVER_DATETIME_FORMAT)
            date_start = \
                first_detail_start < week_start and \
                week_start + ' ' + dt_first_day.strftime('%H:%M:%S') or \
                dt_first_day.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            dt_next_week = \
                datetime.strptime(
                    date_start, DEFAULT_SERVER_DATETIME_FORMAT
                ) + relativedelta(weeks=+1)

            # Determine the appropriate rest day list to use
            #
            restday_ids = False
            date_scheduled_start = \
                datetime.strptime(
                    schedule.date_start, DEFAULT_SERVER_DATETIME_FORMAT
                ).date()
            date_week_start = \
                datetime.strptime(week_start, DEFAULT_SERVER_DATETIME_FORMAT)\
                    .date()
            date_week = relativedelta(days=+7)

            if date_week_start == date_scheduled_start:
                restday_ids = schedule.restday_ids1
            elif date_week_start == date_scheduled_start + date_week:
                restday_ids = schedule.restday_ids2
            elif date_week_start == date_scheduled_start + date_week * 2:
                restday_ids = schedule.restday_ids3
            elif date_week_start == date_scheduled_start + date_week * 3:
                restday_ids = schedule.restday_ids4
            elif date_week_start == date_scheduled_start + date_week * 4:
                restday_ids = schedule.restday_ids5

            # If there is explicit rest day data use it, otherwise try to guess
            # based on which days are not scheduled.
            #
            if restday_ids:
                res = [rd.sequence for rd in restday_ids]
            else:
                weekdays = ['0', '1', '2', '3', '4', '5', '6']
                scheddays = []

                for detail in schedule.detail_ids:
                    # Make sure the date we're examining isn't in the previous week
                    # or the next one
                    detail_date_start = datetime.strptime(
                        detail.date_start, DEFAULT_SERVER_DATETIME_FORMAT
                    )

                    if detail.date_start < week_start or \
                            detail_date_start >= dt_next_week:
                        continue

                    if detail.dayofweek not in scheddays:
                        scheddays.append(detail.dayofweek)

                res = [int(d) for d in weekdays if d not in scheddays]
                # If there are no schedule.details return nothing instead of
                # *ALL* the days in the week
                if len(res) == 7:
                    res = []

        return res

    @api.multi
    @api.onchange('date_start')
    def _onchange_date_start(self):
        for schedule in self:
            if schedule.date_start:
                dt_start = datetime.strptime(
                    schedule.date_start, DEFAULT_SERVER_DATE_FORMAT
                )
                if dt_start.weekday() == 0:
                    dt_end = dt_start + relativedelta(days=+7)
                    schedule.date_end = datetime.strftime(
                        dt_end, DEFAULT_SERVER_DATE_FORMAT
                    )

    @api.multi
    @api.constrains('employee_id', 'date_start')
    def onchange_employee_start_date(self):
        for schedule in self:
            date_start = schedule.date_start

            if date_start:
                date_start = datetime.strptime(schedule.date_start, '%Y-%m-%d').date()
                # The schedule must start on a Monday
                if date_start.weekday() != 0:
                    raise UserError(_("The starting date of the schedule must start on mondays"))
                else:
                    date_end = date_start + relativedelta(days=+6)
                    schedule.date_end = date_end

            if schedule.employee_id.name:
                schedule.name = schedule.employee_id.name

                if date_start:
                    schedule.name = "{}: {} Wk {}".format(
                        schedule.name,
                        date_start.strftime('%Y-%m-%d'),
                        str(date_start.isocalendar()[1])
                    )

    @api.multi
    def delete_details(self):
        self.write({'detail_ids': [(5, 0, 0)]})

    @api.multi
    def add_restdays(self, field_name, rest_days=None):
        for schedule in self:
            restday_ids = []

            if not rest_days:
                for rd in schedule.template_id.restday_ids:
                    restday_ids.append(rd.id)
            else:
                restday_ids = self.env['hr.schedule.weekday'].search([
                    ('sequence', 'in', rest_days)
                ]).mapped('id')

            if len(restday_ids) > 0:
                schedule.write({
                    field_name: [(6, 0, restday_ids)]
                })

    @api.model
    def create_details(self, schedules):
        leave_obj = self.env['hr.holidays']

        for schedule in schedules.filtered(lambda item: item.template_id and
                                           item.date_start and item.date_end):
            leaves = []
            leave_ids = leave_obj.search([
                ('employee_id', '=', schedule.employee_id.id),
                ('date_from', '<=', schedule.date_end),
                ('date_to', '>=', schedule.date_start)
            ])

            for lv in leave_ids:
                utc_dt_from = \
                    utc.localize(
                        datetime.strptime(
                            lv.date_from, DEFAULT_SERVER_DATETIME_FORMAT
                        ), is_dst=False
                    )
                utc_dt_to = \
                    utc.localize(
                        datetime.strptime(
                            lv.date_to, DEFAULT_SERVER_DATETIME_FORMAT
                        ), is_dst=False
                    )

                leaves.append((utc_dt_from, utc_dt_to))

            local_tz = utc if not self.env.user.tz else timezone(self.env.user.tz)
            schedule_date_iter = \
                datetime.strptime(schedule.date_start, '%Y-%m-%d').date()
            schedule_date_end = \
                datetime.strptime(schedule.date_end, '%Y-%m-%d').date()
            schedule_week_start = schedule_date_iter
            schedule_date_start = schedule_date_iter
            date_week = relativedelta(days=+7)

            while schedule_date_iter <= schedule_date_end:
                # Enter the rest day(s)
                #
                if schedule_date_iter == schedule_date_start:
                    self.add_restdays('restday_ids1')
                elif schedule_date_iter == schedule_date_start + date_week:
                    self.add_restdays('restday_ids2')
                elif schedule_date_iter == schedule_date_start + date_week * 2:
                    self.add_restdays('restday_ids3')
                elif schedule_date_iter == schedule_date_start + date_week * 3:
                    self.add_restdays('restday_ids4')
                elif schedule_date_iter == schedule_date_start + date_week * 4:
                    self.add_restdays('restday_ids5')

                prev_utc_dt_start = False
                prev_day_of_week = False

                for worktime in schedule.template_id.worktime_ids:
                    from_hour, from_separator, from_minute = \
                        worktime.hour_from.partition(':')
                    to_hour, to_separator, to_minute = \
                        worktime.hour_to.partition(':')
                    if len(from_separator) == 0 or len(to_separator) == 0:
                        raise UserError(
                            _('The time should be entered as HH:MM')
                        )

                    # TODO - Someone affected by DST should fix this
                    #
                    dt_start = datetime.strptime(
                        schedule_week_start.strftime('%Y-%m-%d') + ' ' +
                        from_hour + ':' + from_minute + ':00',
                        '%Y-%m-%d %H:%M:%S'
                    )
                    local_dt_start = local_tz.localize(dt_start, is_dst=False)
                    utc_dt_start = local_dt_start.astimezone(utc)

                    if worktime.dayofweek != 0:
                        utc_dt_start = \
                            utc_dt_start + \
                            relativedelta(days=+int(worktime.dayofweek))

                    date_day = utc_dt_start.astimezone(local_tz).date()

                    # If this worktime is a continuation (i.e - after lunch)
                    # set the start time based on the difference from the
                    # previous record
                    #
                    if prev_day_of_week and \
                            prev_day_of_week == worktime.dayofweek:
                        prev_hour = prev_utc_dt_start.strftime('%H')
                        prev_minutes = prev_utc_dt_start.strftime('%M')
                        current_hour = utc_dt_start.strftime('%H')
                        current_minutes = utc_dt_start.strftime('%M')
                        delta_seconds = (
                            datetime.strptime(
                                current_hour + ':' + current_minutes, '%H:%M'
                            ) - datetime.strptime(
                                prev_hour + ':' + prev_minutes, '%H:%M'
                            )
                        ).seconds
                        utc_dt_start = prev_utc_dt_start + \
                                       timedelta(seconds=+delta_seconds)
                        date_day = prev_utc_dt_start.astimezone(local_tz).date()

                    delta_seconds = (
                        datetime.strptime(
                            to_hour + ':' + to_minute, '%H:%M'
                        ) - datetime.strptime(
                            from_hour + ':' + from_minute, '%H:%M'
                        )
                    ).seconds
                    utc_dt_end = utc_dt_start + timedelta(seconds=+delta_seconds)

                    # Leave empty holes where there are leaves
                    #
                    _skip = False
                    for utc_dt_from, utc_dt_to in leaves:
                        if utc_dt_from <= utc_dt_start and \
                                utc_dt_to >= utc_dt_end:
                            _skip = True
                            break
                        elif utc_dt_start < utc_dt_from <= utc_dt_end:
                            if utc_dt_to == utc_dt_end:
                                _skip = True
                            else:
                                utc_dt_end = utc_dt_from + timedelta(seconds=-1)
                            break
                        elif utc_dt_start <= utc_dt_to < utc_dt_end:
                            if utc_dt_to == utc_dt_end:
                                _skip = True
                            else:
                                utc_dt_start = utc_dt_to + timedelta(seconds=+1)
                            break

                    if not _skip:
                        val = {
                            'name': schedule.name,
                            'dayofweek': worktime.dayofweek,
                            'day': date_day,
                            'date_start': utc_dt_start.strftime(
                                '%Y-%m-%d %H:%M:%S'),
                            'date_end': utc_dt_end.strftime(
                                '%Y-%m-%d %H:%M:%S'),
                            'schedule_id': schedule.id,
                        }
                        schedule.write({
                            'detail_ids': [(0, 0, val)]
                        })

                    prev_day_of_week = worktime.dayofweek
                    prev_utc_dt_start = utc_dt_start

                schedule_date_iter = schedule_week_start + relativedelta(weeks=+1)
                schedule_week_start = schedule_date_iter

        return True

    @api.multi
    def write(self, vals):
        result = super(HrSchedule, self).write(vals)

        schedules = self.filtered(
            lambda schedule: 'template_id' in vals or
                             'date_start' in vals or 'date_end' in vals
        )
        if schedules:
            self.delete_details()
            self.create_details(schedules)

        return result

    @api.model
    def create(self, vals):
        self._check_overlapping_schedules(vals)

        result = super(HrSchedule, self).create(vals)

        return result

    @api.model
    def create_mass_schedule(self):
        """
        Creates tentative schedules for all employees based on the
        schedule template attached to their contract. Called from the
        scheduler.
        """

        schedule_obj = self.env['hr.schedule']
        employee_obj = self.env['hr.employee']
        department_obj = self.env['hr.department']

        # Create a two-week schedule beginning from Monday of next week.
        #
        dt = datetime.today()
        days = 7 - dt.weekday()
        dt += relativedelta(days=+days)
        date_start = dt.date()
        date_end = date_start + relativedelta(weeks=+2, days=-1)

        # Create schedules for each employee in each department
        #
        departments = department_obj.search([])
        for department in departments:
            employees = employee_obj.search([
                ('department_id', '=', department.id),
            ], order="name")

            if len(employees) == 0:
                continue

            for employee in employees:
                if (
                    not employee.contract_id
                    or not employee.contract_id.schedule_template_id
                ):
                    continue

                schedule_vals = {
                    'name':(
                            employee.name + ': ' \
                            + date_start.strftime('%Y-%m-%d') + ' Wk ' \
                            + str(date_start.isocalendar()[1])
                            ),
                    'employee_id': employee.id,
                    'template_id': employee.contract_id.schedule_template_id.id,
                    'date_start': date_start.strftime('%Y-%m-%d'),
                    'date_end': date_end.strftime('%Y-%m-%d'),
                }

                schedule_obj.create(schedule_vals)

    @api.multi
    def delete_table(self):
        is_successful = True

        for schedule in self:
            if schedule.state not in ['draft', 'unlocked']:
                is_successful = False
            for detail in schedule.detail_ids:
                if detail.state not in ['draft', 'unlocked']:
                    is_successful

        return is_successful

    @api.multi
    def unlink(self):
        for schedule in self:
            # Do not remove schedules that are not in draft or unlocked state
            if not self.delete_table():
                continue

            # Delete the schedule details associated with this schedule
            #
            if len(schedule.detail_ids) > 0:
                schedule.detail_ids.unlink()

        return super(HrSchedule, self).unlink()

    @api.multi
    def button_confirm(self):
        self.filtered(lambda schedule: schedule.state == "draft").write({
            'state': 'confirmed'
        })

    @api.multi
    def button_lock(self):
        self.filtered(lambda schedule: schedule.state == "confirmed").write({
            'state': 'locked'
        })

    @api.multi
    def button_draft(self):
        self.filtered(lambda schedule: schedule.state == "confirmed").write({
            'state': "draft"
        })
