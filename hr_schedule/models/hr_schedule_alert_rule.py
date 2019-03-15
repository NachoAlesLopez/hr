# -*- coding: utf-8 -*-

class hr_schedule_alert_rule(orm.Model):

    _name = 'hr.schedule.alert.rule'
    _description = 'Scheduling/Attendance Exception Rule'

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=10, required=True),
        'severity': fields.selection((
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ), 'Severity', required=True),
        'grace_period': fields.integer(
            'Grace Period',
            help='In the case of early or late rules, the amount of time '
                 'before/after the scheduled time that the rule will trigger.'
        ),
        'window': fields.integer('Window of Activation'),
        'active': fields.boolean('Active'),
    }

    _defaults = {
        'active': True,
        'severity': 'low',
    }

    def check_rule(self, cr, uid, rule, sched_details, punches, context=None):
        """Identify if the schedule detail or attendance records
        trigger any rule. If they do return the datetime and id of the
        record that triggered it in one of the appropriate lists.
        All schedule detail and attendance records are expected to be
        in sorted order according to datetime.
        """

        res = {'schedule_details': [], 'punches': []}

        if rule.code == 'MISSPUNCH':
            prev = False
            for punch in punches:
                if not prev:
                    prev = punch
                    if punch.action != 'sign_in':
                        res['punches'].append((punch.name, punch.id))
                elif prev.action == 'sign_in':
                    if punch.action != 'sign_out':
                        res['punches'].append((punch.name, punch.id))
                elif prev.action == 'sign_out':
                    if punch.action != 'sign_in':
                        res['punches'].append((punch.name, punch.id))
                prev = punch
            if len(punches) > 0 and prev.action != 'sign_out':
                res['punches'].append((punch.name, punch.id))
        elif rule.code == 'UNSCHEDATT':
            for punch in punches:
                if punch.action == 'sign_in':
                    isMatch = False
                    dtPunch = datetime.strptime(
                        punch.name, '%Y-%m-%d %H:%M:%S')
                    for detail in sched_details:
                        dtSched = datetime.strptime(
                            detail.date_start, '%Y-%m-%d %H:%M:%S')
                        difference = 0
                        if dtSched >= dtPunch:
                            difference = abs((dtSched - dtPunch).seconds) / 60
                        else:
                            difference = abs((dtPunch - dtSched).seconds) / 60
                        if difference < rule.window:
                            isMatch = True
                            break
                    if not isMatch:
                        res['punches'].append((punch.name, punch.id))
        elif rule.code == 'MISSATT':
            if len(sched_details) > len(punches):
                for detail in sched_details:
                    isMatch = False
                    dtSched = datetime.strptime(
                        detail.date_start, '%Y-%m-%d %H:%M:%S')
                    for punch in punches:
                        if punch.action == 'sign_in':
                            dtPunch = datetime.strptime(
                                punch.name, '%Y-%m-%d %H:%M:%S')
                            difference = 0
                            if dtSched >= dtPunch:
                                difference = (dtSched - dtPunch).seconds / 60
                            else:
                                difference = (dtPunch - dtSched).seconds / 60
                            if difference < rule.window:
                                isMatch = True
                                break
                    if not isMatch:
                        res['schedule_details'].append(
                            (detail.date_start, detail.id))
        elif rule.code == 'UNSCHEDOT':
            actual_hours = 0
            sched_hours = 0
            for detail in sched_details:
                dtStart = datetime.strptime(
                    detail.date_start, '%Y-%m-%d %H:%M:%S')
                dtEnd = datetime.strptime(detail.date_end, '%Y-%m-%d %H:%M:%S')
                sched_hours += float((dtEnd - dtStart).seconds / 60) / 60.0

            dtStart = False
            for punch in punches:
                if punch.action == 'sign_in':
                    dtStart = datetime.strptime(
                        punch.name, '%Y-%m-%d %H:%M:%S')
                elif punch.action == 'sign_out':
                    dtEnd = datetime.strptime(punch.name, '%Y-%m-%d %H:%M:%S')
                    actual_hours += float(
                        (dtEnd - dtStart).seconds / 60) / 60.0
                    if actual_hours > 8 >= sched_hours:
                        res['punches'].append((punch.name, punch.id))
        elif rule.code == 'TARDY':
            for detail in sched_details:
                isMatch = False
                dtSched = datetime.strptime(
                    detail.date_start, '%Y-%m-%d %H:%M:%S')
                for punch in punches:
                    if punch.action == 'sign_in':
                        dtPunch = datetime.strptime(
                            punch.name, '%Y-%m-%d %H:%M:%S')
                        difference = 0
                        if dtPunch > dtSched:
                            difference = (dtPunch - dtSched).seconds / 60
                        if rule.window > difference > rule.grace_period:
                            isMatch = True
                            break
                if isMatch:
                    res['punches'].append((punch.name, punch.id))
        elif rule.code == 'LVEARLY':
            for detail in sched_details:
                isMatch = False
                dtSched = datetime.strptime(
                    detail.date_end, '%Y-%m-%d %H:%M:%S')
                for punch in punches:
                    if punch.action == 'sign_out':
                        dtPunch = datetime.strptime(
                            punch.name, '%Y-%m-%d %H:%M:%S')
                        difference = 0
                        if dtPunch < dtSched:
                            difference = (dtSched - dtPunch).seconds / 60
                        if rule.window > difference > rule.grace_period:
                            isMatch = True
                            break
                if isMatch:
                    res['punches'].append((punch.name, punch.id))
        elif rule.code == 'INEARLY':
            for detail in sched_details:
                isMatch = False
                dtSched = datetime.strptime(
                    detail.date_start, '%Y-%m-%d %H:%M:%S')
                for punch in punches:
                    if punch.action == 'sign_in':
                        dtPunch = datetime.strptime(
                            punch.name, '%Y-%m-%d %H:%M:%S')
                        difference = 0
                        if dtPunch < dtSched:
                            difference = (dtSched - dtPunch).seconds / 60
                        if rule.window > difference > rule.grace_period:
                            isMatch = True
                            break
                if isMatch:
                    res['punches'].append((punch.name, punch.id))
        elif rule.code == 'OUTLATE':
            for detail in sched_details:
                isMatch = False
                dtSched = datetime.strptime(
                    detail.date_end, '%Y-%m-%d %H:%M:%S')
                for punch in punches:
                    if punch.action == 'sign_out':
                        dtPunch = datetime.strptime(
                            punch.name, '%Y-%m-%d %H:%M:%S')
                        difference = 0
                        if dtPunch > dtSched:
                            difference = (dtPunch - dtSched).seconds / 60
                        if rule.window > difference > rule.grace_period:
                            isMatch = True
                            break
                if isMatch:
                    res['punches'].append((punch.name, punch.id))
        elif rule.code == 'OVRLP':
            leave_obj = self.pool.get('hr.holidays')
            for punch in punches:
                if punch.action == 'sign_in':
                    dtStart = datetime.strptime(
                        punch.name, '%Y-%m-%d %H:%M:%S')
                elif punch.action == 'sign_out':
                    dtEnd = datetime.strptime(punch.name, '%Y-%m-%d %H:%M:%S')
                    leave_ids = leave_obj.search(
                        cr, uid, [('employee_id', '=', punch.employee_id.id),
                                  ('type', '=', 'remove'),
                                  ('date_from', '<=', dtEnd.strftime(
                                      OE_DTFORMAT)),
                                  ('date_to', '>=', dtStart.strftime(
                                      OE_DTFORMAT)),
                                  ('state', 'in', ['validate', 'validate1'])],
                        context=context)
                    if len(leave_ids) > 0:
                        res['punches'].append((punch.name, punch.id))
                        break

        return res

