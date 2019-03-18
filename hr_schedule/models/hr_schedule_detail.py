# -*- coding: utf-8 -*-
from datetime import timedelta, time, datetime, timezone
from dateutil import relativedelta

from odoo import fields, api, models
from odoo.workflow import trg_validate
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


class HrScheduleDetail(models.Model):
    _name = "hr.schedule.detail"
    _description = "Schedule Detail"
    _order = 'schedule_id, date_start, dayofweek'

    def _day_compute(self, cr, uid, ids, field_name, args, context=None):
        res = dict.fromkeys(ids, '')
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = time.strftime(
                '%Y-%m-%d', time.strptime(obj.date_start, '%Y-%m-%d %H:%M:%S'))
        return res

    def _get_ids_from_sched(self, cr, uid, ids, context=None):
        res = []
        for sched in self.pool.get('hr.schedule').browse(
                cr, uid, ids, context=context):
            for detail in sched.detail_ids:
                res.append(detail.id)
        return res

    name = fields.Char(
        string="Name", size=64, required=True,
    )
    dayofweek = fields.Selection(
        selection=DAYOFWEEK_SELECTION, string='Day of Week', required=True,
        select=True, default=0
    )
    date_start = fields.Datetime(
        string='Start Date and Time', required=True
    )
    date_end = fields.Datetime(
        string='End Date and Time', required=True,
    )
    day = fields.Date(
        string='Day', required=True, select=1
    )
    schedule_id = fields.Many2one(
        comodel_name='hr.schedule', string='Schedule', required=True
    )
    department_id = fields.Many2one(
        comodel_name='hr.department', related='schedule_id.department_id',
        string='Department', store=True
    )
    employee_id = fields.Many2one(
        related='schedule_id.employee_id', comodel_name='hr.employee',
        string='Employee', store=True
    )
    alert_ids = fields.One2many(
        comodel_name='hr.schedule.alert', inverse_name='sched_detail_id',
        string='Alerts', readonly=True
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('validate', 'Confirmed'),
            ('locked', 'Locked'),
            ('unlocked', 'Unlocked'),
        ], string='State', required=True, readonly=True, default="draft"
    )

    @api.model
    def _detail_date(self):
        for detail in self:
            self.env.cr.execute("""\
SELECT id
FROM hr_schedule_detail
WHERE (date_start <= %s and %s <= date_end)
  AND schedule_id=%s
  AND id <> %s
""",
                                (detail.date_end,
                                    detail.date_start,
                                    detail.schedule_id.id,
                                    detail.id)
                                )
            if self.env.cr.fetchall():
                return False

        return True

    _constraints = [
        (_detail_date, 'You cannot have scheduled days that overlap!',
         ['date_start', 'date_end']),
    ]

    @api.model
    def scheduled_hours_on_day(self, employee_id, contract_id, dt):
        dt_delta = timedelta(seconds=0)
        shifts = self.scheduled_begin_end_times(employee_id, contract_id, dt)

        for start, end in shifts:
            dt_delta += end - start

        return float(dt_delta.seconds / 60) / 60.0

    @api.model
    def scheduled_begin_end_times(self, employee_id, contract_id, dt):
        """
        Returns a list of tuples containing shift start and end
        times for the day
        """
        res = []
        details = self.search([
            ('schedule_id.employee_id.id', '=', employee_id),
            ('day', '=', dt.strftime('%Y-%m-%d')),
        ], order='date_start')

        for detail in details:
            res.append(
                (
                    datetime.strptime(detail.date_start, '%Y-%m-%d %H:%M:%S'),
                    datetime.strptime(detail.date_end, '%Y-%m-%d %H:%M:%S')
                )
            )

        return res

    def scheduled_hours_on_day_from_range(self, d, range_dict):
        dt_delta = timedelta(seconds=0)
        shifts = range_dict[d.strftime(DEFAULT_SERVER_DATETIME_FORMAT)]

        for start, end in shifts:
            dt_delta += end - start

        return float(dt_delta.seconds / 60) / 60.0

    def scheduled_begin_end_times_range(self, employee_id, contract_id,
                                        date_start, date_end):
        """Returns a dictionary with the dates in range dtStart - dtEnd
        as keys and a list of tuples containing shift start and end
        times during those days as values
        """

        res = {}
        date = date_start
        while date <= date_end:
            res.update({date.strftime(DEFAULT_SERVER_DATETIME_FORMAT): []})
            date += timedelta(days=+1)

        details = self.search([
            ('schedule_id.employee_id.id', '=', employee_id),
            ('day', '>=', date_start.strftime('%Y-%m-%d')),
            ('day', '<=', date_end.strftime('%Y-%m-%d')),
        ], order='date_start')

        if len(details) > 0:
            for detail in details:
                res[detail.day].append((
                    datetime.strptime(detail.date_start, '%Y-%m-%d %H:%M:%S'),
                    datetime.strptime(detail.date_end, '%Y-%m-%d %H:%M:%S'),
                ))

        return res

    @api.multi
    def _remove_direct_alerts(self):
        """Remove alerts directly attached to the schedule detail and
        return a unique list of tuples of employee id and schedule
        detail date.
        """
        alert_obj = self.env['hr.schedule.alert']

        # Remove alerts directly attached to these schedule details
        #
        alerts = self.env['hr.schedule.alert']
        scheds = []
        sched_keys = []

        for detail in self:
            alerts += detail.alert_ids

            # Hmm, creation of this record triggers a workflow action that
            # tries to write to it. But it seems that computed fields aren't
            # available at this stage. So, use a fallback and compute the day
            # ourselves.
            day = detail.day

            if not detail.day:
                day = time.strftime(
                    '%Y-%m-%d',
                    time.strptime(detail.date_start, '%Y-%m-%d %H:%M:%S')
                )

            key = str(detail.schedule_id.employee_id.id) + day

            if key not in sched_keys:
                scheds.append((detail.schedule_id.employee_id.id, day))
                sched_keys.append(key)

        if len(alerts) > 0:
            alerts.unlink()

        return scheds

    @api.model
    def _recompute_alerts(self, attendances):
        """Recompute alerts for each record in schedule detail."""
        alert_obj = self.env['hr.schedule.alert']
        user = self.env.user
        data = user.tz

        # Remove all alerts for the employee(s) for the day and recompute.
        #
        for employee, str_day in attendances:
            # Today's records will be checked tomorrow. Future records can't
            # generate alerts.
            if str_day >= fields.Date.context_today():
                continue

            # TODO - Someone who cares about DST should fix this
            #
            dt = datetime.strptime(str_day + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
            local_dt = timezone(data['tz']).localize(dt, is_dst=False)
            utc_dt = local_dt.astimezone(timezone.utc)
            utc_dt_next_day = utc_dt + relativedelta(days=+1)
            str_day_start = utc_dt.strftime('%Y-%m-%d %H:%M:%S')
            str_next_day = utc_dt_next_day.strftime('%Y-%m-%d %H:%M:%S')

            alerts = alert_obj.search([
                ('employee_id', '=', employee),
                '&',
                ('name', '>=', str_day_start),
                ('name', '<', str_next_day)
            ])
            alerts.unlink()
            alert_obj.compute_alerts_by_employee(employee, str_day)

    @api.model
    def create(self, vals):
        local_tz = self.env.user.tz

        if 'day' not in vals and 'date_start' in vals:
            # TODO - Someone affected by DST should fix this
            #
            dt_start = datetime.strptime(
                vals['date_start'], DEFAULT_SERVER_DATETIME_FORMAT
            )
            local_dt_start = local_tz.localize(dt_start, is_dst=False)
            utc_dt_start = local_dt_start.astimezone(timezone.utc)
            day_date = utc_dt_start.astimezone(local_tz).date()
            vals['day'] = day_date

        res = super(HrScheduleDetail, self).create(
            vals
        )

        attendances = [
            (
                res.schedule_id.employee_id.id, fields.Date.context_today(),
            ),
        ]
        self._recompute_alerts(attendances)

        return res

    @api.model
    def unlink(self):
        editable_details = self.env['hr.schedule.detail']

        for detail in self:
            if detail.state in ['draft', 'unlocked']:
                editable_details.append(detail.id)

        # Remove alerts directly attached to the schedule details
        #
        attendances = self._remove_direct_alerts(editable_details)

        res = super(HrScheduleDetail, self).unlink()

        # Remove all alerts for the employee(s) for the day and recompute.
        #
        self._recompute_alerts(attendances)

        return res

    @api.multi
    def write(self, vals):
        # Flag for checking wether we have to recompute alerts
        trigger_alert = False

        if 'date_start' in vals or 'date_end' in vals:
            trigger_alert = True

        if trigger_alert:
            # Remove alerts directly attached to the attendances
            #
            attendances = self._remove_direct_alerts()

        res = super(HrScheduleDetail, self).write(vals)

        if trigger_alert:
            # Remove all alerts for the employee(s) for the day and recompute.
            #
            self._recompute_alerts(attendances)

        return res

    @api.multi
    def workflow_lock(self):
        for detail in self:
            self.write({'state': 'locked'})
            trg_validate('hr.schedule', detail.schedule_id.id, 'signal_lock')

        return True

    @api.multi
    def workflow_unlock(self, cr, uid, ids, context=None):
        for detail in self:
            self.write({'state': 'unlocked'})
            trg_validate('hr.schedule', detail.schedule_id.id, 'signal_unlock')

        return True
