# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pytz import timezone, utc

from odoo import fields, api, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class HrScheduleAlert(models.Model):
    _name = 'hr.schedule.alert'
    _description = 'Attendance Exception'
    _inherit = ['mail.thread', 'resource.calendar']

    @api.multi
    def _get_employee_id(self):
        res = {}

        for alert in self:
            if alert.punch_id:
                res[alert.id] = alert.punch_id.employee_id.id
            elif alert.sched_detail_id:
                res[alert.id] = alert.sched_detail_id.schedule_id.employee_id.id
            else:
                res[alert.id] = False

        return res

    name = fields.Datetime(
        string='Date and Time',
        required=True,
        readonly=True
    )
    rule_id = fields.Many2one(
        comodel_name='hr.schedule.alert.rule',
        string='Alert Rule',
        required=True,
        readonly=True
    )
    punch_id = fields.Many2one(
        comodel_name='hr.attendance',
        string='Triggering Punch',
        readonly=True
    )
    sched_detail_id = fields.Many2one(
        comodel_name='hr.schedule.detail',
        string='Schedule Detail',
        readonly=True,
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        compute="_get_employee_id",
        string='Employee',
        store=True
    )
    department_id = fields.Many2one(
        comodel_name='hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True,
        readonly=True
    )
    severity = fields.Selection(
        string='Severity',
        related='rule_id.severity',
        store=True,
        readonly=True
    )
    state = fields.Selection(
        selection=[
            ('unresolved', 'Unresolved'),
            ('resolved', 'Resolved'),
        ],
        string='State',
        readonly=True,
        default='unresolved'
    )

    _sql_constraints = [
        ('all_unique', 'UNIQUE(punch_id,sched_detail_id,name,rule_id)',
         'Duplicate Record!'),
    ]

    def check_for_alerts(self):
        """
        Check the schedule detail and attendance records for
        yesterday against the scheduling/attendance alert rules.
        If any rules match create a record in the database.
        """

        department_obj = self.pool.get('hr.department')
        detail_obj = self.pool.get('hr.schedule.detail')
        attendance_obj = self.pool.get('hr.attendance')
        rule_obj = self.pool.get('hr.schedule.alert.rule')
        local_tz = utc if not self.env.user.tz else timezone(self.env.user.tz)

        # TODO - Someone who cares about DST should fix ths
        #
        dt_today = \
            datetime.strptime(
                datetime.now().strftime('%Y-%m-%d') + ' 00:00:00',
                '%Y-%m-%d %H:%M:%S'
            )
        local_dt_today = \
            local_tz.localize(dt_today, is_dst=False)
        utc_dt_today = local_dt_today.astimezone(timezone.utc)
        utd_dt_yesterday = utc_dt_today + relativedelta(days=-1)
        date_str_today = utc_dt_today.strftime('%Y-%m-%d %H:%M:%S')
        date_str_yesterday = utd_dt_yesterday.strftime('%Y-%m-%d %H:%M:%S')

        departments = department_obj.search([])
        for department in departments:
            for employee in department.member_ids:
                # Get schedule and attendance records for the employee for the
                # day
                #
                schedule_details = detail_obj.search([
                    ('schedule_id.employee_id', '=', employee.id),
                    '&',
                    ('date_start', '>=', date_str_yesterday),
                    ('date_start', '<', date_str_today),
                ], order='date_start')
                attendances = attendance_obj.search([
                    ('employee_id', '=', employee.id),
                    '&',
                    ('name', '>=', date_str_yesterday),
                    ('name', '<', date_str_today),
                ], order='name')

                # Run the schedule and attendance records against each active
                # rule, and create alerts for each result returned.
                #
                rules = rule_obj.search([('active', '=', True)])
                for rule in rules:
                    res = rule_obj.check_rule(
                        rule, schedule_details, attendances
                    )

                    for str_attendance_date, attendance in res['punches']:
                        # skip if it has already been triggered
                        alerts = self.search([
                            ('punch_id', '=', attendance.id),
                            ('rule_id', '=', rule.id),
                            ('name', '=', str_attendance_date),
                        ])

                        if len(alerts) > 0:
                            continue

                        self.create({
                            'name': str_attendance_date,
                            'rule_id': rule.id,
                            'punch_id': attendance,
                        })

                    for str_attendance_date, detail_id in \
                            res['schedule_details']:
                        # skip if it has already been triggered
                        alerts = self.search([
                            ('sched_detail_id', '=', detail_id),
                            ('rule_id', '=', rule.id),
                            ('name', '=', str_attendance_date),
                        ])

                        if len(alerts) > 0:
                            continue

                        self.create({
                            'name': str_attendance_date,
                            'rule_id': rule.id,
                            'sched_detail_id': detail_id,
                        })

    @api.model
    def _get_normalized_attendance(self, employee, utc_dt, attendances):
        attendance_obj = self.env['hr.attendance']
        str_date_today = utc_dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        # If the first punch is a punch-out then get the corresponding punch-in
        # from the previous day.
        #
        if len(attendances) > 0 and attendances[0].action != 'sign_in':
            str_date_yesterday = (
                utc_dt - timedelta(days=+1)
            ).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            yesterday_attendances = attendance_obj.search([
                ('employee', '=', employee),
                '&',
                ('name', '>=', str_date_yesterday),
                ('name', '<', str_date_today)
            ])

            if len(yesterday_attendances) > 0 and yesterday_attendances[-1].action == 'sign_in':
                attendances = [yesterday_attendances[-1].id] + attendances
            else:
                attendances = attendances[1:]

        # If the last punch is a punch-in then get the corresponding punch-out
        # from the next day.
        #
        if len(attendances) > 0 and attendances[-1].action != 'sign_out':
            str_tomorrow = (
                utc_dt + timedelta(days=1)
            ).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            tomorrow_attendances = attendance_obj.search([
                ('employee', '=', employee),
                '&',
                ('name', '>=', str_date_today),
                ('name', '<', str_tomorrow)
            ])

            if len(tomorrow_attendances) > 0 and tomorrow_attendances[0].action == 'sign_out':
                attendances = attendances + [tomorrow_attendances[0].id]
            else:
                attendances = attendances[:-1]

        return attendances

    @api.model
    def compute_alerts_by_employee(self, employee, str_date):
        """
        Compute alerts for employee on specified day.
        """
        detail_obj = self.env['hr.schedule.detail']
        atnd_obj = self.env['hr.attendance']
        rule_obj = self.env['hr.schedule.alert.rule']
        local_tz = utc if not self.env.user.tz else timezone(self.env.user.tz)

        # TODO - Someone who cares about DST should fix ths
        #
        dt = datetime.strptime(str_date + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
        local_dt = local_tz.localize(dt, is_dst=False)
        utc_dt = local_dt.astimezone(utc)
        utc_dt_next_day = utc_dt + relativedelta(days=+1)
        str_today = utc_dt.strftime('%Y-%m-%d %H:%M:%S')
        str_next_day = utc_dt_next_day.strftime('%Y-%m-%d %H:%M:%S')

        # Get schedule and attendance records for the employee for the day
        #
        schedule_details = detail_obj.search([
            ('schedule_id.employee_id', '=', employee.id),
            '&',
            ('day', '>=', str_today),
            ('day', '<', str_next_day),
        ], order='date_start')
        attendances = atnd_obj.search([
            ('employee_id', '=', employee.id),
            '&',
            ('check_in', '>=', str_today),
            ('check_in', '<', str_next_day),
        ], order='check_in')

        attendances = self._get_normalized_attendance(
            employee, utc_dt, attendances
        )

        # Run the schedule and attendance records against each active rule, and
        # create alerts for each result returned.
        #
        rules = rule_obj.search([('active', '=', True)])
        for rule in rules:
            res = rule_obj.check_rule(
                rule, schedule_details, attendances
            )

            for str_dt, attendance in res['punches']:
                # skip if it has already been triggered
                ids = self.search([
                    ('punch_id', '=', attendance.id),
                    ('rule_id', '=', rule.id),
                    ('name', '=', str_dt),
                ])
                if len(ids) > 0:
                    continue

                self.create({
                    'name': str_dt,
                    'rule_id': rule.id,
                    'punch_id': attendance
                })

            for str_dt, detail_id in res['schedule_details']:
                # skip if it has already been triggered
                ids = self.search([
                    ('sched_detail_id', '=', detail_id),
                    ('rule_id', '=', rule.id),
                    ('name', '=', str_dt)
                ])
                if len(ids) > 0:
                    continue

                self.create({
                    'name': str_dt,
                    'rule_id': rule.id,
                    'sched_detail_id': detail_id
                })

