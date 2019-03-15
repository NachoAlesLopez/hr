# -*- coding: utf-8 -*-

class hr_schedule_request(orm.Model):

    _name = 'hr.schedule.request'
    _description = 'Change Request'

    _inherit = ['mail.thread']

    _columns = {
        'employee_id': fields.many2one(
            'hr.employee',
            'Employee',
            required=True,
        ),
        'date': fields.date(
            'Date',
            required=True,
        ),
        'type': fields.selection(
            [
                ('missedp', 'Missed Punch'),
                ('adjp', 'Punch Adjustment'),
                ('absence', 'Absence'),
                ('schedadj', 'Schedule Adjustment'),
                ('other', 'Other'),
            ],
            'Type',
            required=True,
        ),
        'message': fields.text(
            'Message',
        ),
        'state': fields.selection(
            [
                ('pending', 'Pending'),
                ('auth', 'Authorized'),
                ('denied', 'Denied'),
                ('cancel', 'Cancelled'),
            ],
            'State',
            required=True,
            readonly=True,
        ),
    }
    _defaults = {
        'state': 'pending',
    }

