# -*- coding: utf-8 -*-

class hr_schedule_working_times(orm.Model):

    _name = "hr.schedule.template.worktime"
    _description = "Work Detail"

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
        'hour_from': fields.char(
            'Work From',
            size=5,
            required=True,
            select=True,
        ),
        'hour_to': fields.char(
            "Work To",
            size=5,
            required=True,
        ),
        'template_id': fields.many2one(
            'hr.schedule.template',
            'Schedule Template',
            required=True,
        ),
    }
    _order = 'dayofweek, name'

    def _rec_message(self, cr, uid, ids, context=None):
        return _('Duplicate Records!')

    _sql_constraints = [
        ('unique_template_day_from',
         'UNIQUE(template_id, dayofweek, hour_from)', _rec_message),
        ('unique_template_day_to',
         'UNIQUE(template_id, dayofweek, hour_to)', _rec_message),
    ]

    _defaults = {
        'dayofweek': '0'
    }
