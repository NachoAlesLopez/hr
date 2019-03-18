# -*- coding: utf-8 -*-
from odoo import fields, models


class HrWeekDay(models.Model):
    _name = 'hr.schedule.weekday'
    _description = 'Days of the Week'

    name = fields.Char(
        string='Name', size=64, required=True
    )
    sequence = fields.Integer(
        string='Sequence', required=True
    )
