# -*- coding: utf-8 -*-

class hr_attendance(orm.Model):

    _name = 'hr.attendance'
    _inherit = 'hr.attendance'
    _columns = {
        'alert_ids': fields.one2many(
            'hr.schedule.alert',
            'punch_id',
            'Exceptions',
            readonly=True,
        ),
    }

    def _remove_direct_alerts(self, cr, uid, ids, context=None):
        """Remove alerts directly attached to the attendance and return
        a unique list of tuples of employee ids and attendance dates.
        """

        alert_obj = self.pool.get('hr.schedule.alert')

        # Remove alerts directly attached to the attendances
        #
        alert_ids = []
        attendances = []
        attendance_keys = []
        for attendance in self.browse(cr, uid, ids, context=context):
            [alert_ids.append(alert.id) for alert in attendance.alert_ids]
            key = str(attendance.employee_id.id) + attendance.day
            if key not in attendance_keys:
                attendances.append((attendance.employee_id.id, attendance.day))
                attendance_keys.append(key)

        if len(alert_ids) > 0:
            alert_obj.unlink(cr, uid, alert_ids, context=context)

        return attendances

    def _recompute_alerts(self, cr, uid, attendances, context=None):
        """Recompute alerts for each record in attendances."""

        alert_obj = self.pool.get('hr.schedule.alert')

        # Remove all alerts for the employee(s) for the day and recompute.
        #
        for ee_id, strDay in attendances:

            # Today's records will be checked tomorrow. Future records can't
            # generate alerts.
            if strDay >= fields.date.context_today(
                    self, cr, uid, context=context):
                continue

            # TODO - Someone who cares about DST should fix this
            #
            data = self.pool.get('res.users').read(
                cr, uid, uid, ['tz'], context=context)
            dt = datetime.strptime(strDay + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
            lcldt = timezone(data['tz']).localize(dt, is_dst=False)
            utcdt = lcldt.astimezone(utc)
            utcdtNextDay = utcdt + relativedelta(days=+1)
            strDayStart = utcdt.strftime('%Y-%m-%d %H:%M:%S')
            strNextDay = utcdtNextDay.strftime('%Y-%m-%d %H:%M:%S')

            alert_ids = alert_obj.search(
                cr, uid, [
                    ('employee_id', '=', ee_id),
                    '&',
                    ('name', '>=', strDayStart),
                    ('name', '<', strNextDay)
                ], context=context)
            alert_obj.unlink(cr, uid, alert_ids, context=context)
            alert_obj.compute_alerts_by_employee(
                cr, uid, ee_id, strDay, context=context)

    def create(self, cr, uid, vals, context=None):

        res = super(hr_attendance, self).create(cr, uid, vals, context=context)

        obj = self.browse(cr, uid, res, context=context)
        attendances = [
            (
                obj.employee_id.id, fields.date.context_today(
                    self, cr, uid, context=context
                )
            )
        ]
        self._recompute_alerts(cr, uid, attendances, context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):

        # Remove alerts directly attached to the attendances
        #
        attendances = self._remove_direct_alerts(cr, uid, ids, context=context)

        res = super(hr_attendance, self).unlink(cr, uid, ids, context=context)

        # Remove all alerts for the employee(s) for the day and recompute.
        #
        self._recompute_alerts(cr, uid, attendances, context=context)

        return res

    def write(self, cr, uid, ids, vals, context=None):

        # Flag for checking wether we have to recompute alerts
        trigger_alert = False
        for k, v in vals.iteritems():
            if k in ['name', 'action']:
                trigger_alert = True

        if trigger_alert:
            # Remove alerts directly attached to the attendances
            #
            attendances = self._remove_direct_alerts(
                cr, uid, ids, context=context)

        res = super(hr_attendance, self).write(
            cr, uid, ids, vals, context=context)

        if trigger_alert:
            # Remove all alerts for the employee(s) for the day and recompute.
            #
            self._recompute_alerts(cr, uid, attendances, context=context)

        return res

