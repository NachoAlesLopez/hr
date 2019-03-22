# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo import fields, api, models
from odoo.exceptions import  UserError


class HrScheduleTemplate(models.Model):
    _name = 'hr.schedule.template'
    _description = 'Employee Working Schedule Template'

    name = fields.Char(
        string="Name", size=64, required=True
    )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', required=False,
        default=lambda self: self.env.user.company_id
    )
    worktime_ids = fields.One2many(
        comodel_name='hr.schedule.template.worktime',
        inverse_name='template_id', string='Working Time',
    )
    restday_ids = fields.Many2many(
        comodel_name='hr.schedule.weekday',
        relation='schedule_template_restdays_rel', column1='sched_id',
        column2='weekday_id', string='Rest Days'
    )
    schedule_ids = fields.One2many(
        comodel_name="hr.schedule", inverse_name="template_id",
        readonly=1, string="Schedules"
    )

    @api.multi
    def get_rest_days(self):
        """
        If the rest day(s) have been explicitly specified that's
        what is returned, otherwise a guess is returned based on the
        week days that are not scheduled. If an explicit rest day(s)
        has not been specified an empty list is returned. If it is able
        to figure out the rest days it will return a list of week day
        integers with Monday being 0.
        """
        for template in self:
            if template.restday_ids:
                res = [rest_day.sequence for rest_day in template.restday_ids]
            else:
                weekdays = ['0', '1', '2', '3', '4', '5', '6']
                scheddays = [
                    working_time.dayofweek
                    for working_time in template.worktime_ids
                    if working_time.dayofweek not in scheddays
                ]
                res = [int(d) for d in weekdays if d not in scheddays]

                # If there are no work days return nothing instead of *ALL* the
                # days in the week
                if len(res) == 7:
                    res = []

        return res

    @api.multi
    def get_hours_by_weekday(self, day_no):
        """Return the number working hours in the template for day_no.
        For day_no 0 is Monday.
        """
        delta = timedelta(seconds=0)

        for template in self:
            for worktime in template.worktime_ids:
                if int(worktime.dayofweek) != day_no:
                    continue

                from_hour, from_separator, from_minute = \
                    worktime.hour_from.partition(':')
                to_hour, to_separator, to_minute = \
                    worktime.hour_to.partition(':')

                if len(from_separator) == 0 or len(to_separator) == 0:
                    raise UserError(_('Format of working hours is incorrect'))

                delta += (
                    datetime.strptime(to_hour + ':' + to_minute, '%H:%M') -
                    datetime.strptime(from_hour + ':' + from_minute, '%H:%M')
                )

        return float(delta.seconds / 60) / 60.0

