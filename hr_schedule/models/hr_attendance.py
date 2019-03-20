# -*- coding: utf-8 -*-
from datetime import datetime
from dateutil import relativedelta
from pytz import timezone, utc

from odoo import fields, api, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'
    
    alert_ids = fields.One2many(
        comodel_name='hr.schedule.alert', inverse_name='punch_id',
        string='Exceptions', readonly=True
    )

    @api.multi
    def _remove_direct_alerts(self):
        """
        Remove alerts directly attached to the attendance and return
        a unique list of tuples of employee ids and attendance dates.
        """
        # Remove alerts directly attached to the attendances
        #
        alerts = self.env['hr.schedule.alert']
        attendances = []
        attendance_keys = []

        for attendance in self:
            alerts = alerts + attendance.alert_ids
            key = str(attendance.employee_id.id) + attendance.day
            if key not in attendance_keys:
                attendances.append((attendance.employee_id, attendance.day))
                attendance_keys.append(key)

        if len(alerts) > 0:
            alerts.unlink()

        return attendances

    @api.multi
    def _recompute_alerts(self, attendances):
        """
        Recompute alerts for each record in attendances.
        """
        alert_obj = self.env['hr.schedule.alert']

        # Remove all alerts for the employee(s) for the day and recompute.
        #
        for employee, str_day in attendances:
            # Today's records will be checked tomorrow. Future records can't
            # generate alerts.
            if str_day >= fields.Date.context_today():
                continue

            # TODO - Someone who cares about DST should fix this
            #
            local_tz = utc if not self.env.user.tz else timezone(self.env.user.tz)
            dt = datetime.strptime(str_day + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
            local_dt = local_tz.localize(dt, is_dst=False)
            utc_dt = local_dt.astimezone(utc)
            utc_dt_next_day = utc_dt + relativedelta(days=+1)
            str_day_start = utc_dt.strftime('%Y-%m-%d %H:%M:%S')
            str_next_day = utc_dt_next_day.strftime('%Y-%m-%d %H:%M:%S')

            alerts = alert_obj.search([
                ('employee_id', '=', employee),
                '&',
                ('name', '>=', str_day_start),
                ('name', '<', str_next_day)
            ])
            alerts.unlink(alerts)
            alerts.compute_alerts_by_employee(employee, str_day)

    @api.model
    def create(self, vals):
        res = super(HrAttendance, self).create(vals)

        attendances = [
            (
                res.employee_id, fields.Date.context_today()
            )
        ]
        res._recompute_alerts(attendances)

        return res

    @api.multi
    def unlink(self):
        # Remove alerts directly attached to the attendances
        #
        attendances = self._remove_direct_alerts()

        res = super(HrAttendance, self).unlink()

        # Remove all alerts for the employee(s) for the day and recompute.
        #
        self.env['hr.attendance']._recompute_alerts(attendances)

        return res

    @api.multi
    def write(self, vals):
        # Flag for checking wether we have to recompute alerts
        trigger_alert = False

        if 'name' in vals or 'action' in vals:
            trigger_alert = True

        if trigger_alert:
            # Remove alerts directly attached to the attendances
            #
            attendances = self._remove_direct_alerts()

        res = super(HrAttendance, self).write(vals)

        if trigger_alert:
            # Remove all alerts for the employee(s) for the day and recompute.
            #
            self._recompute_alerts(attendances)

        return res

