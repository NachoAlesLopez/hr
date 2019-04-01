# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import fields, api, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class HrScheduleAlertRule(models.Model):
    _name = 'hr.schedule.alert.rule'
    _description = 'Scheduling/Attendance Exception Rule'

    name = fields.Char(string='Name', size=64, required=True)
    code = fields.Char(string='Code', size=10, required=True)
    severity = fields.Selection(
        selection=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical')
        ], string='Severity', required=True, default='low'
    )
    grace_period = fields.Integer(
        string='Grace Period',
        help='In the case of early or late rules, the amount of time '
             'before/after the scheduled time that the rule will trigger.'
    )
    window = fields.Integer(
        string='Window of Activation'
    )
    active = fields.Boolean(
        string='Active', default=True
    )

    def check_rule(self, rule, schedule_details, punches):
        """
        Identify if the schedule detail or attendance records
        trigger any rule. If they do return the datetime and id of the
        record that triggered it in one of the appropriate lists.
        All schedule detail and attendance records are expected to be
        in sorted order according to datetime.
        """
        res = {
            'schedule_details': [],
            'punches': []
        }

        if rule.code == 'MISSPUNCH':
            # Se le olvida hacer "salida" o "entrada" cuando debe.
            for punch in punches.filtered(
                lambda att: not att.check_in and att.check_out
            ):
                res['punches'].append((punch.name, punch.id))
        elif rule.code == 'UNSCHEDATT':
            for punch in punches:
                is_match = False

                for punch_type in ['check_in', 'check_out']:
                    dt_punch = datetime.strptime(
                        punch[punch_type], '%Y-%m-%d %H:%M:%S'
                    )

                    for detail in schedule_details:
                        dt_schedule = datetime.strptime(
                            detail.date_start, '%Y-%m-%d %H:%M:%S'
                        )
                        difference = 0

                        if dt_schedule >= dt_punch:
                            difference = \
                                abs((dt_schedule - dt_punch).seconds) / 60
                        else:
                            difference = \
                                abs((dt_punch - dt_schedule).seconds) / 60

                        if difference < rule.window:
                            is_match = True
                            break
                    if is_match:
                        break

                if not is_match:
                    res['punches'].append((punch[punch_type], punch.id))
        elif rule.code == 'MISSATT':
            if len(schedule_details) > len(punches):
                for detail in schedule_details:
                    is_match = False
                    dt_schedule = datetime.strptime(
                        detail.date_start, '%Y-%m-%d %H:%M:%S'
                    )

                    for punch in punches:
                        dt_punch = datetime.strptime(
                            punch.check_in, '%Y-%m-%d %H:%M:%S'
                        )
                        difference = 0

                        if dt_schedule >= dt_punch:
                            difference = \
                                (dt_schedule - dt_punch).seconds / 60
                        else:
                            difference = \
                                (dt_punch - dt_schedule).seconds / 60

                        if difference < rule.window:
                            is_match = True
                            break

                    if not is_match:
                        res['schedule_details'].append(
                            (detail.date_start, detail.id))

        elif rule.code == 'UNSCHEDOT':
            actual_hours = 0
            schedule_hours = 0

            for detail in schedule_details:
                dt_start = datetime.strptime(
                    detail.date_start, '%Y-%m-%d %H:%M:%S'
                )
                dt_end = datetime.strptime(detail.date_end, '%Y-%m-%d %H:%M:%S')
                schedule_hours += \
                    float((dt_end - dt_start).seconds / 60) / 60.0

            for punch in punches:
                dt_start = datetime.strptime(
                    punch.check_in, DEFAULT_SERVER_DATETIME_FORMAT
                )
                dt_end = datetime.strptime(
                    punch.check_out, DEFAULT_SERVER_DATETIME_FORMAT
                )

                actual_hours += float(
                    (dt_end - dt_start).seconds / 60
                ) / 60.0

                # TODO Puede que haga falta cambiar esto,
                # hardcoded a 8 horas al día
            if actual_hours >= schedule_hours and len(punches) > 0:
                res['punches'].append((punches[0].check_in, punch.id))
        elif rule.code == 'TARDY':
            for detail in schedule_details:
                is_match = False
                dt_schedule = datetime.strptime(
                    detail.date_start, '%Y-%m-%d %H:%M:%S'
                )

                for punch in punches:
                    if punch.check_in:
                        dt_punch = datetime.strptime(
                            punch.check_in, '%Y-%m-%d %H:%M:%S'
                        )
                        difference = 0

                        if dt_punch > dt_schedule:
                            difference = (dt_punch - dt_schedule).seconds / 60
                        if rule.window > difference > rule.grace_period:
                            is_match = True
                            break

                if is_match:
                    res['punches'].append((punch.check_in, punch.id))
        elif rule.code == 'LVEARLY':
            for detail in schedule_details:
                is_match = False
                dt_schedule = datetime.strptime(
                    detail.date_end, '%Y-%m-%d %H:%M:%S'
                )

                for punch in punches:
                    if punch.check_out:
                        dt_punch = datetime.strptime(
                            punch.check_out, '%Y-%m-%d %H:%M:%S'
                        )
                        difference = 0

                        if dt_punch < dt_schedule:
                            difference = (dt_schedule - dt_punch).seconds / 60
                        if rule.window > difference > rule.grace_period:
                            is_match = True
                            break

                if is_match:
                    res['punches'].append((punch.check_out, punch.id))
        elif rule.code == 'INEARLY':
            for detail in schedule_details:
                is_match = False
                dt_schedule = datetime.strptime(
                    detail.date_start, '%Y-%m-%d %H:%M:%S'
                )

                for punch in punches:
                    if punch.check_in:
                        dt_punch = datetime.strptime(
                            punch.check_in, '%Y-%m-%d %H:%M:%S'
                        )
                        difference = 0

                        if dt_punch < dt_schedule:
                            difference = (dt_schedule - dt_punch).seconds / 60
                        if rule.window > difference > rule.grace_period:
                            is_match = True
                            break

                if is_match:
                    res['punches'].append((punch.check_in, punch.id))
        elif rule.code == 'OUTLATE':
            for detail in schedule_details:
                is_match = False
                dt_schedule = datetime.strptime(
                    detail.date_end, '%Y-%m-%d %H:%M:%S'
                )

                for punch in punches:
                    if punch.check_out:
                        dt_punch = datetime.strptime(
                            punch.check_out, '%Y-%m-%d %H:%M:%S'
                        )
                        difference = 0

                        if dt_punch > dt_schedule:
                            difference = (dt_punch - dt_schedule).seconds / 60
                        if rule.window > difference > rule.grace_period:
                            is_match = True
                            break

                if is_match:
                    res['punches'].append((punch.check_out, punch.id))
        elif rule.code == 'OVRLP':
            leave_obj = self.env['hr.holidays']

            for punch in punches:
                dt_start = datetime.strptime(
                    punch.check_in, DEFAULT_SERVER_DATETIME_FORMAT
                )
                dt_end = datetime.strptime(
                    punch.check_out, DEFAULT_SERVER_DATETIME_FORMAT
                )

                leaves = leave_obj.search([
                    ('employee_id', '=', punch.employee_id.id),
                    ('type', '=', 'remove'),
                    ('date_from', '<=', dt_end.strftime(
                        DEFAULT_SERVER_DATETIME_FORMAT)),
                    ('date_to', '>=', dt_start.strftime(
                        DEFAULT_SERVER_DATETIME_FORMAT)),
                    ('state', 'in', ['validate', 'validate1'])
                ])
                if len(leaves) > 0:
                    res['punches'].append((punch.check_in, punch.id))
                    break

        return res

