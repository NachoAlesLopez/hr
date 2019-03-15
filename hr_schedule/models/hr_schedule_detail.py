# -*- coding: utf-8 -*-

class schedule_detail(orm.Model):
    _name = "hr.schedule.detail"
    _description = "Schedule Detail"

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

    _columns = {
        'name': fields.char(
            "Name",
            size=64,
            required=True,
        ),
        'dayofweek': fields.selection(
            DAYOFWEEK_SELECTION,
            'Day of Week',
            required=True,
            select=True,
        ),
        'date_start': fields.datetime(
            'Start Date and Time',
            required=True,
        ),
        'date_end': fields.datetime(
            'End Date and Time',
            required=True,
        ),
        'day': fields.date(
            'Day',
            required=True,
            select=1,
        ),
        'schedule_id': fields.many2one(
            'hr.schedule',
            'Schedule',
            required=True,
        ),
        'department_id': fields.related(
            'schedule_id',
            'department_id',
            type='many2one',
            relation='hr.department',
            string='Department',
            store=True,
        ),
        'employee_id': fields.related(
            'schedule_id',
            'employee_id',
            type='many2one',
            relation='hr.employee',
            string='Employee',
            store=True,
        ),
        'alert_ids': fields.one2many(
            'hr.schedule.alert',
            'sched_detail_id',
            'Alerts',
            readonly=True,
        ),
        'state': fields.selection(
            [
                ('draft', 'Draft'),
                ('validate', 'Confirmed'),
                ('locked', 'Locked'),
                ('unlocked', 'Unlocked'),
            ],
            'State',
            required=True,
            readonly=True,
        ),
    }
    _order = 'schedule_id, date_start, dayofweek'
    _defaults = {
        'dayofweek': '0',
        'state': 'draft',
    }

    def _detail_date(self, cr, uid, ids, context=None):
        for dtl in self.browse(cr, uid, ids, context=context):
            cr.execute("""\
SELECT id
FROM hr_schedule_detail
WHERE (date_start <= %s and %s <= date_end)
  AND schedule_id=%s
  AND id <> %s""", (dtl.date_end, dtl.date_start, dtl.schedule_id.id, dtl.id))
            if cr.fetchall():
                return False
        return True

    def _rec_message(self, cr, uid, ids, context=None):
        return _('You cannot have scheduled days that overlap!')

    _constraints = [
        (_detail_date, _rec_message, ['date_start', 'date_end']),
    ]

    def scheduled_hours_on_day(
            self, cr, uid, employee_id, contract_id, dt, context=None):
        dtDelta = timedelta(seconds=0)
        shifts = self.scheduled_begin_end_times(
            cr, uid, employee_id, contract_id, dt, context=context
        )
        for start, end in shifts:
            dtDelta += end - start
        return float(dtDelta.seconds / 60) / 60.0

    def scheduled_begin_end_times(
            self, cr, uid, employee_id, contract_id, dt, context=None):
        """Returns a list of tuples containing shift start and end
        times for the day
        """

        res = []
        detail_ids = self.search(cr, uid, [
            ('schedule_id.employee_id.id', '=', employee_id),
            ('day', '=', dt.strftime(
                '%Y-%m-%d')),
        ],
            order='date_start',
            context=context)
        if len(detail_ids) > 0:
            sched_details = self.browse(cr, uid, detail_ids, context=context)
            for detail in sched_details:
                res.append((
                    datetime.strptime(
                        detail.date_start, '%Y-%m-%d %H:%M:%S'),
                    datetime.strptime(
                        detail.date_end, '%Y-%m-%d %H:%M:%S'),
                ))

        return res

    def scheduled_hours_on_day_from_range(self, d, range_dict):

        dtDelta = timedelta(seconds=0)
        shifts = range_dict[d.strftime(OE_DFORMAT)]
        for start, end in shifts:
            dtDelta += end - start

        return float(dtDelta.seconds / 60) / 60.0

    def scheduled_begin_end_times_range(
        self, cr, uid, employee_id, contract_id,
            dStart, dEnd, context=None):
        """Returns a dictionary with the dates in range dtStart - dtEnd
        as keys and a list of tuples containing shift start and end
        times during those days as values
        """

        res = {}
        d = dStart
        while d <= dEnd:
            res.update({d.strftime(OE_DFORMAT): []})
            d += timedelta(days=+1)

        detail_ids = self.search(cr, uid, [
            ('schedule_id.employee_id.id', '=', employee_id),
            ('day', '>=', dStart.strftime(
                '%Y-%m-%d')),
            ('day', '<=', dEnd.strftime(
                '%Y-%m-%d')),
        ],
            order='date_start',
            context=context)
        if len(detail_ids) > 0:
            sched_details = self.browse(cr, uid, detail_ids, context=context)
            for detail in sched_details:
                res[detail.day].append((
                    datetime.strptime(
                        detail.date_start, '%Y-%m-%d %H:%M:%S'),
                    datetime.strptime(
                        detail.date_end, '%Y-%m-%d %H:%M:%S'),
                ))

        return res

    def _remove_direct_alerts(self, cr, uid, ids, context=None):
        """Remove alerts directly attached to the schedule detail and
        return a unique list of tuples of employee id and schedule
        detail date.
        """

        if isinstance(ids, (int, long)):
            ids = [ids]

        alert_obj = self.pool.get('hr.schedule.alert')

        # Remove alerts directly attached to these schedule details
        #
        alert_ids = []
        scheds = []
        sched_keys = []
        for sched_detail in self.browse(cr, uid, ids, context=context):

            [alert_ids.append(alert.id) for alert in sched_detail.alert_ids]

            # Hmm, creation of this record triggers a workflow action that
            # tries to write to it. But it seems that computed fields aren't
            # available at this stage. So, use a fallback and compute the day
            # ourselves.
            day = sched_detail.day
            if not sched_detail.day:
                day = time.strftime('%Y-%m-%d', time.strptime(
                    sched_detail.date_start, '%Y-%m-%d %H:%M:%S'))
            key = str(sched_detail.schedule_id.employee_id.id) + day
            if key not in sched_keys:
                scheds.append((sched_detail.schedule_id.employee_id.id, day))
                sched_keys.append(key)

        if len(alert_ids) > 0:
            alert_obj.unlink(cr, uid, alert_ids, context=context)

        return scheds

    def _recompute_alerts(self, cr, uid, attendances, context=None):
        """Recompute alerts for each record in schedule detail."""

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

            alert_ids = alert_obj.search(cr, uid, [
                ('employee_id', '=', ee_id),
                '&',
                ('name', '>=', strDayStart),
                ('name', '<', strNextDay)
            ], context=context)
            alert_obj.unlink(cr, uid, alert_ids, context=context)
            alert_obj.compute_alerts_by_employee(
                cr, uid, ee_id, strDay, context=context)

    def create(self, cr, uid, vals, context=None):

        if 'day' not in vals and 'date_start' in vals:
            # TODO - Someone affected by DST should fix this
            #
            user = self.pool.get('res.users').browse(
                cr, uid, uid, context=context)
            local_tz = timezone(user.tz)
            dtStart = datetime.strptime(vals['date_start'], OE_DTFORMAT)
            locldtStart = local_tz.localize(dtStart, is_dst=False)
            utcdtStart = locldtStart.astimezone(utc)
            dDay = utcdtStart.astimezone(local_tz).date()
            vals.update({'day': dDay})

        res = super(schedule_detail, self).create(
            cr, uid, vals, context=context)

        obj = self.browse(cr, uid, res, context=context)
        attendances = [
            (
                obj.schedule_id.employee_id.id, fields.date.context_today(
                    self, cr, uid, context=context
                ),
            ),
        ]
        self._recompute_alerts(cr, uid, attendances, context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):

        if isinstance(ids, (int, long)):
            ids = [ids]

        detail_ids = []
        for detail in self.browse(cr, uid, ids, context=context):
            if detail.state in ['draft', 'unlocked']:
                detail_ids.append(detail.id)

        # Remove alerts directly attached to the schedule details
        #
        attendances = self._remove_direct_alerts(
            cr, uid, detail_ids, context=context)

        res = super(schedule_detail, self).unlink(
            cr, uid, detail_ids, context=context)

        # Remove all alerts for the employee(s) for the day and recompute.
        #
        self._recompute_alerts(cr, uid, attendances, context=context)

        return res

    def write(self, cr, uid, ids, vals, context=None):

        # Flag for checking wether we have to recompute alerts
        trigger_alert = False
        for k, v in vals.iteritems():
            if k in ['date_start', 'date_end']:
                trigger_alert = True

        if trigger_alert:
            # Remove alerts directly attached to the attendances
            #
            attendances = self._remove_direct_alerts(
                cr, uid, ids, context=context)

        res = super(schedule_detail, self).write(
            cr, uid, ids, vals, context=context)

        if trigger_alert:
            # Remove all alerts for the employee(s) for the day and recompute.
            #
            self._recompute_alerts(cr, uid, attendances, context=context)

        return res

    def workflow_lock(self, cr, uid, ids, context=None):

        wkf = netsvc.LocalService('workflow')
        for detail in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, [detail.id], {
                       'state': 'locked'}, context=context)
            wkf.trg_validate(
                uid, 'hr.schedule', detail.schedule_id.id, 'signal_lock', cr)

        return True

    def workflow_unlock(self, cr, uid, ids, context=None):

        wkf = netsvc.LocalService('workflow')
        for detail in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, [detail.id], {
                       'state': 'unlocked'}, context=context)
            wkf.trg_validate(
                uid, 'hr.schedule', detail.schedule_id.id, 'signal_unlock', cr)

        return True
