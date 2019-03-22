# -*- coding: utf-8 -*-
from odoo import fields, api, models


class HrScheduleRequest(models.Model):
    _name = 'hr.schedule.request'
    _inherit = ['mail.thread']
    _description = 'Change Request'

    employee_id = fields.Many2one(
        comodel_name='hr.employee', string='Employee', required=True
    )
    date = fields.Date(
        string='Date', required=True
    )
    type = fields.Selection(
        selection=[
            ('missedp', 'Missed Punch'),
            ('adjp', 'Punch Adjustment'),
            ('absence', 'Absence'),
            ('schedadj', 'Schedule Adjustment'),
            ('other', 'Other'),
        ], string='Type', required=True
    )
    message = fields.Text(
        string='Message'
    )
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('auth', 'Authorized'),
            ('denied', 'Denied'),
            ('cancel', 'Cancelled'),
        ], string='State', required=True, readonly=True, default='pending'
    )

    name = fields.Char(
        string="Name", compute="_compute_name", store=True
    )

    @api.multi
    @api.depends('employee_id', 'date', 'type')
    def _compute_name(self):
        for request in self:
            request.name = "{employee} {type} ({date})".format(
                employee=request.employee_id.name, type=request.type,
                date=request.date
            )
