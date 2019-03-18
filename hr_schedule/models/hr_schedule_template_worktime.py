# -*- coding: utf-8 -*-
from hr_schedule_detail import DAYOFWEEK_SELECTION

from odoo import fields, models


class HrScheduleWorkingTimes(models.Model):
    _name = "hr.schedule.template.worktime"
    _description = "Work Detail"
    _order = 'dayofweek, name'

    name = fields.Char(
        string="Name", size=64, required=True
    )
    dayofweek = fields.Selection(
        selection=DAYOFWEEK_SELECTION, string='Day of Week', required=True,
        select=True, default=0
    )
    hour_from = fields.Char(
        string='Work From', size=5, required=True, select=True
    )
    hour_to = fields.Char(
        string="Work To", size=5, required=True
    )
    template_id = fields.Many2one(
        comodel_name='hr.schedule.template', string='Schedule Template',
        required=True
    )

    _sql_constraints = [
        ('unique_template_day_from',
         'UNIQUE(template_id, dayofweek, hour_from)', "Duplicate Records!"),
        ('unique_template_day_to',
         'UNIQUE(template_id, dayofweek, hour_to)', "Duplicate Records!"),
    ]
