# -*- coding: utf-8 -*-

class hr_schedule_alert(orm.Model):

    _name = 'hr.schedule.alert'
    _description = 'Attendance Exception'
    _inherit = ['mail.thread', 'resource.calendar']

    def _get_employee_id(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for alrt in self.browse(cr, uid, ids, context=context):
            if alrt.punch_id:
                res[alrt.id] = alrt.punch_id.employee_id.id
            elif alrt.sched_detail_id:
                res[alrt.id] = alrt.sched_detail_id.schedule_id.employee_id.id
            else:
                res[alrt.id] = False

        return res

    _columns = {
        'name': fields.datetime(
            'Date and Time',
            required=True,
            readonly=True,
        ),
        'rule_id': fields.many2one(
            'hr.schedule.alert.rule',
            'Alert Rule',
            required=True,
            readonly=True,
        ),
        'punch_id': fields.many2one(
            'hr.attendance',
            'Triggering Punch',
            readonly=True,
        ),
        'sched_detail_id': fields.many2one(
            'hr.schedule.detail',
            'Schedule Detail',
            readonly=True,
        ),
        'employee_id': fields.function(
            _get_employee_id,
            type='many2one',
            obj='hr.employee',
            method=True,
            store=True,
            string='Employee',
            readonly=True,
        ),
        'department_id': fields.related(
            'employee_id',
            'department_id',
            type='many2one',
            store=True,
            relation='hr.department',
            string='Department',
            readonly=True,
        ),
        'severity': fields.related(
            'rule_id',
            'severity',
            type='char',
            string='Severity',
            store=True,
            readonly=True,
        ),
        'state': fields.selection(
            [
                ('unresolved', 'Unresolved'),
                ('resolved', 'Resolved'),
            ],
            'State',
            readonly=True,
        ),
    }
    _defaults = {
        'state': 'unresolved',
    }

    def _rec_message(self, cr, uid, ids, context=None):
        return _('Duplicate Record!')

    _sql_constraints = [
        ('all_unique', 'UNIQUE(punch_id,sched_detail_id,name,rule_id)',
         _rec_message),
    ]
    _track = {
        'state': {
            'hr_schedule.mt_alert_resolved': (
                lambda self, r, u, obj, ctx=None: obj['state'] == 'resolved'
            ),
            'hr_schedule.mt_alert_unresolved': (
                lambda self, r, u, obj, ctx=None: obj['state'] == 'unresolved'
            ),
        },
    }

    def check_for_alerts(self, cr, uid, context=None):
        """Check the schedule detail and attendance records for
        yesterday against the scheduling/attendance alert rules.
        If any rules match create a record in the database.
        """

        dept_obj = self.pool.get('hr.department')
        detail_obj = self.pool.get('hr.schedule.detail')
        attendance_obj = self.pool.get('hr.attendance')
        rule_obj = self.pool.get('hr.schedule.alert.rule')

        # TODO - Someone who cares about DST should fix ths
        #
        data = self.pool.get('res.users').read(
            cr, uid, uid, ['tz'], context=context)
        dtToday = datetime.strptime(
            datetime.now().strftime('%Y-%m-%d') + ' 00:00:00',
            '%Y-%m-%d %H:%M:%S')
        lcldtToday = timezone(data['tz'] and data['tz'] or 'UTC').localize(
            dtToday, is_dst=False)
        utcdtToday = lcldtToday.astimezone(utc)
        utcdtYesterday = utcdtToday + relativedelta(days=-1)
        strToday = utcdtToday.strftime('%Y-%m-%d %H:%M:%S')
        strYesterday = utcdtYesterday.strftime('%Y-%m-%d %H:%M:%S')

        dept_ids = dept_obj.search(cr, uid, [], context=context)
        for dept in dept_obj.browse(cr, uid, dept_ids, context=context):
            for employee in dept.member_ids:

                # Get schedule and attendance records for the employee for the
                # day
                #
                sched_detail_ids = detail_obj.search(
                    cr, uid, [
                        ('schedule_id.employee_id', '=', employee.id),
                        '&',
                        ('date_start', '>=', strYesterday),
                        ('date_start', '<', strToday),
                    ],
                    order='date_start',
                    context=context
                )
                attendance_ids = attendance_obj.search(
                    cr, uid, [
                        ('employee_id', '=', employee.id),
                        '&',
                        ('name', '>=', strYesterday),
                        ('name', '<', strToday),
                    ],
                    order='name',
                    context=context
                )

                # Run the schedule and attendance records against each active
                # rule, and create alerts for each result returned.
                #
                rule_ids = rule_obj.search(
                    cr, uid, [('active', '=', True)], context=context)
                for rule in rule_obj.browse(
                        cr, uid, rule_ids, context=context):
                    res = rule_obj.check_rule(
                        cr, uid, rule, detail_obj.browse(
                            cr, uid, sched_detail_ids, context=context),
                        attendance_obj.browse(
                            cr, uid, attendance_ids, context=context),
                        context=context
                    )

                    for strdt, attendance_id in res['punches']:
                        # skip if it has already been triggered
                        ids = self.search(
                            cr, uid, [
                                ('punch_id', '=', attendance_id),
                                ('rule_id', '=', rule.id),
                                ('name', '=', strdt),
                            ], context=context)
                        if len(ids) > 0:
                            continue

                        self.create(
                            cr, uid, {
                                'name': strdt,
                                'rule_id': rule.id,
                                'punch_id': attendance_id,
                            }, context=context
                        )

                    for strdt, detail_id in res['schedule_details']:
                        # skip if it has already been triggered
                        ids = self.search(
                            cr, uid, [
                                ('sched_detail_id', '=', detail_id),
                                ('rule_id', '=', rule.id),
                                ('name', '=', strdt),
                            ], context=context)
                        if len(ids) > 0:
                            continue

                        self.create(
                            cr, uid, {
                                'name': strdt,
                                'rule_id': rule.id,
                                'sched_detail_id': detail_id,
                            }, context=context
                        )

    def _get_normalized_attendance(
            self, cr, uid, employee_id, utcdt, att_ids, context=None):

        att_obj = self.pool.get('hr.attendance')
        attendances = att_obj.browse(cr, uid, att_ids, context=context)
        strToday = utcdt.strftime(OE_DTFORMAT)

        # If the first punch is a punch-out then get the corresponding punch-in
        # from the previous day.
        #
        if len(attendances) > 0 and attendances[0].action != 'sign_in':
            strYesterday = (utcdt - timedelta(days=1)).strftime(OE_DTFORMAT)
            ids = att_obj.search(
                cr, uid, [
                    ('employee_id', '=', employee_id),
                    '&',
                    ('name', '>=', strYesterday),
                    ('name', '<', strToday),
                ], order='name', context=context)
            att2 = att_obj.browse(cr, uid, ids, context=context)
            if len(att2) > 0 and att2[-1].action == 'sign_in':
                att_ids = [att2[-1].id] + att_ids
            else:
                att_ids = att_ids[1:]

        # If the last punch is a punch-in then get the corresponding punch-out
        # from the next day.
        #
        if len(attendances) > 0 and attendances[-1].action != 'sign_out':
            strTommorow = (utcdt + timedelta(days=1)).strftime(OE_DTFORMAT)
            ids = att_obj.search(
                cr, uid, [
                    ('employee_id', '=', employee_id),
                    '&',
                    ('name', '>=', strToday),
                    ('name', '<', strTommorow),
                ], order='name', context=context)
            att2 = att_obj.browse(cr, uid, ids, context=context)
            if len(att2) > 0 and att2[0].action == 'sign_out':
                att_ids = att_ids + [att2[0].id]
            else:
                att_ids = att_ids[:-1]

        return att_ids

    def compute_alerts_by_employee(
            self, cr, uid, employee_id, strDay, context=None):
        """Compute alerts for employee on specified day."""

        detail_obj = self.pool.get('hr.schedule.detail')
        atnd_obj = self.pool.get('hr.attendance')
        rule_obj = self.pool.get('hr.schedule.alert.rule')

        # TODO - Someone who cares about DST should fix ths
        #
        data = self.pool.get('res.users').read(
            cr, uid, uid, ['tz'], context=context)
        dt = datetime.strptime(strDay + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
        lcldt = timezone(data['tz']).localize(dt, is_dst=False)
        utcdt = lcldt.astimezone(utc)
        utcdtNextDay = utcdt + relativedelta(days=+1)
        strToday = utcdt.strftime('%Y-%m-%d %H:%M:%S')
        strNextDay = utcdtNextDay.strftime('%Y-%m-%d %H:%M:%S')

        # Get schedule and attendance records for the employee for the day
        #
        sched_detail_ids = detail_obj.search(
            cr, uid, [('schedule_id.employee_id', '=', employee_id),
                      '&',
                      ('day', '>=', strToday),
                      ('day', '<', strNextDay),
                      ],
            order='date_start',
            context=context)
        attendance_ids = atnd_obj.search(
            cr, uid, [('employee_id', '=', employee_id),
                      '&',
                      ('name', '>=', strToday),
                      ('name', '<', strNextDay),
                      ],
            order='name',
            context=context)
        attendance_ids = self._get_normalized_attendance(
            cr, uid, employee_id, utcdt,
            attendance_ids, context)

        # Run the schedule and attendance records against each active rule, and
        # create alerts for each result returned.
        #
        rule_ids = rule_obj.search(
            cr, uid, [('active', '=', True)], context=context)
        for rule in rule_obj.browse(cr, uid, rule_ids, context=context):
            res = rule_obj.check_rule(
                cr, uid, rule,
                detail_obj.browse(cr, uid, sched_detail_ids, context=context),
                atnd_obj.browse(cr, uid, attendance_ids, context=context),
                context=context
            )

            for strdt, attendance_id in res['punches']:
                # skip if it has already been triggered
                ids = self.search(cr, uid, [('punch_id', '=', attendance_id),
                                            ('rule_id', '=', rule.id),
                                            ('name', '=', strdt),
                                            ],
                                  context=context)
                if len(ids) > 0:
                    continue

                self.create(cr, uid, {'name': strdt,
                                      'rule_id': rule.id,
                                      'punch_id': attendance_id},
                            context=context)

            for strdt, detail_id in res['schedule_details']:
                # skip if it has already been triggered
                ids = self.search(
                    cr, uid, [('sched_detail_id', '=', detail_id),
                              ('rule_id', '=', rule.id),
                              ('name', '=', strdt),
                              ],
                    context=context)
                if len(ids) > 0:
                    continue

                self.create(cr, uid, {'name': strdt,
                                      'rule_id': rule.id,
                                      'sched_detail_id': detail_id},
                            context=context)

