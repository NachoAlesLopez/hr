# -*- coding: utf-8 -*-

class week_days(orm.Model):

    _name = 'hr.schedule.weekday'
    _description = 'Days of the Week'

    _columns = {
        'name': fields.char(
            'Name',
            size=64,
            required=True,
        ),
        'sequence': fields.integer(
            'Sequence',
            required=True,
        ),
    }
