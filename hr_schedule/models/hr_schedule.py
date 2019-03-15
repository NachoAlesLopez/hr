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
from datetime import datetime, timezone
from dateutil import relativedelta
from pytz import utc

from odoo import fields, api, models, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

DAYOFWEEK_SELECTION = [
    ('0', 'Monday'),
    ('1', 'Tuesday'),
    ('2', 'Wednesday'),
    ('3', 'Thursday'),
    ('4', 'Friday'),
    ('5', 'Saturday'),
    ('6', 'Sunday'),
]

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
        string="Description", size=64, required=True, readonly=True,
        states={'draft': [('readonly', False)]}
    )

    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', readonly=True,
        default=lambda self: self.env['res.company']
            ._company_default_get('hr.schedule'),
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee', string='Employee', required=True,
        readonly=True, states={'draft': [('readonly', False)]}
    )
    template_id = fields.Many2one(
        comodel_name='hr.schedule.template', string='Schedule Template',
        readonly=True, states={'draft': [('readonly', False)]}
    )
    detail_ids = fields.One2many(
        comodel_name='hr.schedule.detail', inverse_name='schedule_id',
        string='Schedule Detail', readonly=True,
        states={'draft': [('readonly', False)]}
    )
    date_start = fields.Date(
        string='Start Date', required=True, readonly=True,
        states={'draft': [('readonly', False)]}
    )
    date_end = fields.Date(
        string='End Date', required=True, readonly=True,
        states={'draft': [('readonly', False)]}
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
        column1='sched_id', column2='weekday_id', string='Rest Days Week 1'
    )
    restday_ids2 = fields.Many2many(
        comodel_name='hr.schedule.weekday', relation='schedule_restdays_rel2',
        column1='sched_id', column2='weekday_id', string='Rest Days Week 2'
    )
    restday_ids3 = fields.Many2many(
        comodel_name='hr.schedule.weekday', relation='schedule_restdays_rel3',
        column1='sched_id', column2='weekday_id', string='Rest Days Week 3'
    )
    restday_ids4 = fields.Many2many(
        comodel_name='hr.schedule.weekday', relation='schedule_restdays_rel4',
        column1='sched_id', column2='weekday_id', string='Rest Days Week 4'
    )
    restday_ids5 = fields.Many2many(
        comodel_name='hr.schedule.weekday', relation='schedule_restdays_rel5',
        column1='sched_id', column2='weekday_id', string='Rest Days Week 5'
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('validate', 'Confirmed'),
            ('locked', 'Locked'),
            ('unlocked', 'Unlocked'),
        ], string='State', required=True, readonly=True, default='draft'
    )

    @api.multi
    @api.constrains('date_start', 'date_end')
    def _check_overlapping_schedules(self):
        for schedule in self:
            schedules = self.env['hr.schedule'].search([
                ('date_start', '<=', schedule.date_start),
                (schedule.date_end, '<=', 'date_end'),
                ('employee_id', '=', schedule.employee_id.id)
            ])
            if schedules:
                return _('You cannot have schedules that overlap!')
            else:
                return False

    @api.multi  # ?
    def get_rest_days(self, employee_id, datetime):
        """If the rest day(s) have been explicitly specified that's
        what is returned, otherwise a guess is returned based on the
        week days that are not scheduled. If an explicit rest day(s)
        has not been specified an empty list is returned. If it is able
        to figure out the rest days it will return a list of week day
        integers with Monday being 0.
        """
        day = datetime.strftime()
        schedule = self.env['hr.schedule'].search([
            ('employee_id', '=', employee_id.id),
            ('date_start', '<=', day),
            ('date_end', '>=', day),
        ])

        if not schedule:
            return None
        elif len(schedule) > 1:
            raise UserError(
                _('Employee has a scheduled date in more than one schedule.')
            )

        # If the day is in the middle of the week get the start of the week
        if datetime.weekday() == 0:
            week_start = datetime.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        else:
            week_start = (datetime + relativedelta(days=-datetime.weekday()))\
                .strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        return self.get_rest_days_by_id(week_start)

    @api.one  # ?
    def get_rest_days_by_id(self, week_start):
        """If the rest day(s) have been explicitly specified that's
        what is returned, otherwise a guess is returned based on the
        week days that are not scheduled. If an explicit rest day(s)
        has not been specified an empty list is returned. If it is
        able to figure out the rest days it will return a list of week
        day integers with Monday being 0.
        """
        res = []

        # Set the boundaries of the week (i.e- start of current week and start
        # of next week)
        schedule = self
        if not schedule.detail_ids:
            return res

        dt_first_day = \
            datetime.strptime(schedule.detail_ids[0].date_start,
                              DEFAULT_SERVER_DATETIME_FORMAT)
        date_start = \
            dt_first_day.strftime(DEFAULT_SERVER_DATETIME_FORMAT) < week_start \
            and week_start + ' ' + dt_first_day.strftime('%H:%M:%S') or \
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
            datetime.strptime(week_start, DEFAULT_SERVER_DATETIME_FORMAT).date()

        if date_week_start == date_scheduled_start:
            restday_ids = schedule.restday_ids1
        elif date_week_start == date_scheduled_start + relativedelta(days=+7):
            restday_ids = schedule.restday_ids2
        elif date_week_start == date_scheduled_start + relativedelta(days=+14):
            restday_ids = schedule.restday_ids3
        elif date_week_start == date_scheduled_start + relativedelta(days=+21):
            restday_ids = schedule.restday_ids4
        elif date_week_start == date_scheduled_start + relativedelta(days=+28):
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
            # If there are no schedule.details return nothing instead of *ALL*
            # the days in the week
            if len(res) == 7:
                res = []

        return res

    @api.onchange('employee_id', 'date_start')  # ?
    def onchange_employee_start_date(self, employee, date_start):
        date_start = False

        if self.date_start:
            date_start = datetime.strptime(self.date_start, '%Y-%m-%d').date()
            # The schedule must start on a Monday
            if date_start.weekday() != 0:
                self.date_start = False
                self.date_end = False
            else:
                date_end = date_start + relativedelta(days=+6)
                self.date_end = date_end

        if self.employee.name:
            self.name = self.employee.name

            if date_start:
                self.name = self.name + ': ' + date_start.strftime('%Y-%m-%d') \
                            + ' Wk ' + str(date_start.isocalendar()[1])

        if self.employee.contract_id:
            contract = self.employee.mapped('contract_id')

            if contract.schedule_template_id:
                self.template_id = contract[0]['schedule_template_id']

    def delete_details(self):
        self.write({'detail_ids': [6, 0, 0]})

    @api.multi
    def add_restdays(self, field_name, rest_days):
        for schedule in self:
            restday_ids = []

            if not rest_days:
                for rd in schedule.template_id.restday_ids:
                    restday_ids.append(rd.id)
            else:
                restday_ids = self.env['hr.schedule.weekday'].search([
                    ('sequence', 'in', rest_days)
                ])

            if len(restday_ids) > 0:
                self.write({
                    field_name: [(6, 0, restday_ids)]
                })

    @api.multi
    def create_details(self):
        leave_obj = self.pool.get('hr.holidays')

        for schedule in self.filtered(lambda item: item.template_id):
            leaves = []
            leave_ids = leave_obj.search([
                ('employee_id', '=', schedule.employee_id.id),
                ('date_from', '<=', schedule.date_end),
                ('date_to', '>=', schedule.date_start),
                ('state', 'in', ['draft', 'validate', 'validate1'])
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

            user = self.env.uid
            local_tz = timezone(user.tz)
            schedule_date_iter = \
                datetime.strptime(schedule.date_start, '%Y-%m-%d').date()
            schedule_date_end = \
                datetime.strptime(schedule.date_end, '%Y-%m-%d').date()
            schedule_week_start = schedule_date_iter
            schedule_date_start = schedule_date_iter

            while schedule_date_iter <= schedule_date_end:
                # Enter the rest day(s)
                #
                if schedule_date_iter == schedule_date_start:
                    self.add_restdays(schedule, 'restday_ids1')
                elif schedule_date_iter == schedule_date_start + \
                        relativedelta(days=+7):
                    self.add_restdays(schedule, 'restday_ids2')
                elif schedule_date_iter == schedule_date_start + \
                        relativedelta(days=+14):
                    self.add_restdays(schedule, 'restday_ids3')
                elif schedule_date_iter == schedule_date_start +\
                        relativedelta(days=+21):
                    self.add_restdays(schedule, 'restday_ids4')
                elif schedule_date_iter == schedule_date_start + \
                        relativedelta(days=+28):
                    self.add_restdays(schedule, 'restday_ids5')

                prevutcdtStart_variable_rara = False
                prevDayofWeek_variable_rara = False
                for worktime in schedule.template_id.worktime_ids:
                    hour, sep, minute = worktime.hour_from.partition(':')
                    to_hour, sep2, to_minute = worktime.hour_to.partition(':')
                    if len(sep) == 0 or len(sep2) == 0:
                        raise UserError(
                            _('The time should be entered as HH:MM')
                        )

                    # TODO - Someone affected by DST should fix this
                    #
                    dt_start = datetime.strptime(
                        schedule_week_start.strftime('%Y-%m-%d') + ' ' + hour +
                        ':' + minute + ':00', '%Y-%m-%d %H:%M:%S'
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
                    if prevDayofWeek_variable_rara and prevDayofWeek_variable_rara == worktime.dayofweek:
                        prevHour = prevutcdtStart_variable_rara.strftime('%H')
                        prevMin = prevutcdtStart_variable_rara.strftime('%M')
                        curHour = utc_dt_start.strftime('%H')
                        curMin = utc_dt_start.strftime('%M')
                        delta_seconds = (
                            datetime.strptime(curHour + ':' + curMin, '%H:%M')
                            - datetime.strptime(prevHour + ':' + prevMin,
                                                '%H:%M')).seconds
                        utc_dt_start = prevutcdtStart_variable_rara + \
                                       timedelta(seconds=+delta_seconds)
                        date_day = prevutcdtStart_variable_rara.astimezone(local_tz).date()

                    delta_seconds = (datetime.strptime(to_hour + ':' + to_minute,
                                                       '%H:%M')
                                     - datetime.strptime(hour + ':' + minute,
                                                         '%H:%M')).seconds
                    utcdtEnd = utc_dt_start + timedelta(seconds=+delta_seconds)

                    # Leave empty holes where there are leaves
                    #
                    _skip = False
                    for utc_dt_from, utc_dt_to in leaves:
                        if utc_dt_from <= utc_dt_start and utc_dt_to >= utcdtEnd:
                            _skip = True
                            break
                        elif utc_dt_start < utc_dt_from <= utcdtEnd:
                            if utc_dt_to == utcdtEnd:
                                _skip = True
                            else:
                                utcdtEnd = utc_dt_from + timedelta(seconds=-1)
                            break
                        elif utc_dt_start <= utc_dt_to < utcdtEnd:
                            if utc_dt_to == utcdtEnd:
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
                            'date_end': utcdtEnd.strftime(
                                '%Y-%m-%d %H:%M:%S'),
                            'schedule_id': sched_id,
                        }
                        self.write(cr, uid, sched_id, {
                                   'detail_ids': [(0, 0, val)]},
                                   context=context)

                    prevDayofWeek_variable_rara = worktime.dayofweek
                    prevutcdtStart_variable_rara = utc_dt_start

                schedule_date_iter = schedule_week_start + relativedelta(weeks=+1)
                schedule_week_start = schedule_date_iter

        return True

    def create(self, cr, uid, vals, context=None):

        my_id = super(hr_schedule, self).create(cr, uid, vals, context=context)

        self.create_details(cr, uid, my_id, context=context)

        return my_id

    def create_mass_schedule(self, cr, uid, context=None):
        """Creates tentative schedules for all employees based on the
        schedule template attached to their contract. Called from the
        scheduler.
        """

        sched_obj = self.pool.get('hr.schedule')
        ee_obj = self.pool.get('hr.employee')

        # Create a two-week schedule beginning from Monday of next week.
        #
        dt = datetime.today()
        days = 7 - dt.weekday()
        dt += relativedelta(days=+days)
        dStart = dt.date()
        dEnd = dStart + relativedelta(weeks=+2, days=-1)

        # Create schedules for each employee in each department
        #
        dept_ids = self.pool.get('hr.department').search(cr, uid, [],
                                                         context=context)
        for dept in self.pool.get('hr.department').browse(cr, uid, dept_ids,
                                                          context=context):
            ee_ids = ee_obj.search(cr, uid, [
                ('department_id', '=', dept.id),
            ], order="name", context=context)
            if len(ee_ids) == 0:
                continue

            for ee in ee_obj.browse(cr, uid, ee_ids, context=context):

                if (not ee.contract_id
                        or not ee.contract_id.schedule_template_id):
                    continue

                sched = {
                    'name': (ee.name + ': ' + dStart.strftime('%Y-%m-%d') +
                             ' Wk ' + str(dStart.isocalendar()[1])),
                    'employee_id': ee.id,
                    'template_id': ee.contract_id.schedule_template_id.id,
                    'date_start': dStart.strftime('%Y-%m-%d'),
                    'date_end': dEnd.strftime('%Y-%m-%d'),
                }
                sched_obj.create(cr, uid, sched, context=context)

    def deletable(self, cr, uid, sched_id, context=None):

        sched = self.browse(cr, uid, sched_id, context=context)
        if sched.state not in ['draft', 'unlocked']:
            return False
        for detail in sched.detail_ids:
            if detail.state not in ['draft', 'unlocked']:
                return False

        return True

    def unlink(self, cr, uid, ids, context=None):

        detail_obj = self.pool.get('hr.schedule.detail')

        if isinstance(ids, (int, long)):
            ids = [ids]

        schedule_ids = []
        for schedule in self.browse(cr, uid, ids, context=context):
            # Do not remove schedules that are not in draft or unlocked state
            if not self.deletable(cr, uid, schedule.id, context):
                continue

            # Delete the schedule details associated with this schedule
            #
            detail_ids = []
            [detail_ids.append(detail.id) for detail in schedule.detail_ids]
            if len(detail_ids) > 0:
                detail_obj.unlink(cr, uid, detail_ids, context=context)

            schedule_ids.append(schedule.id)

        return super(hr_schedule, self).unlink(
            cr, uid, schedule_ids, context=context)

    def _workflow_common(self, cr, uid, ids, signal, next_state, context=None):

        wkf = netsvc.LocalService('workflow')
        for sched in self.browse(cr, uid, ids, context=context):
            for detail in sched.detail_ids:
                wkf.trg_validate(
                    uid, 'hr.schedule.detail', detail.id, signal, cr)
            self.write(
                cr, uid, sched.id, {'state': next_state}, context=context)
        return True

    def workflow_validate(self, cr, uid, ids, context=None):
        return self._workflow_common(
            cr, uid, ids, 'signal_validate', 'validate', context=context)

    def details_locked(self, cr, uid, ids, context=None):

        for sched in self.browse(cr, uid, ids, context=context):
            for detail in sched.detail_ids:
                if detail.state != 'locked':
                    return False

        return True

    def workflow_lock(self, cr, uid, ids, context=None):
        """Lock the Schedule Record. Expects to be called by its
        schedule detail records as they are locked one by one.
        When the last one has been locked the schedule will also be
        locked.
        """

        all_locked = True
        for sched in self.browse(cr, uid, ids, context=context):
            if self.details_locked(cr, uid, [sched.id], context):
                self.write(cr, uid, sched.id, {
                           'state': 'locked'}, context=context)
            else:
                all_locked = False

        return all_locked

    def workflow_unlock(self, cr, uid, ids, context=None):
        """Unlock the Schedule Record. Expects to be called by its
        schedule detail records as they are unlocked one by one.
        When the first one has been unlocked the schedule will also be
        unlocked.
        """

        all_locked = True
        for sched in self.browse(cr, uid, ids, context=context):
            if not self.details_locked(cr, uid, [sched.id], context):
                self.write(
                    cr, uid, sched.id, {'state': 'unlocked'}, context=context)
            else:
                all_locked = False

        return all_locked is False



