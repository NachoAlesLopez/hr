# -*- coding: utf-8 -*-

class hr_contract(orm.Model):

    _name = 'hr.contract'
    _inherit = 'hr.contract'
    _columns = {
        'schedule_template_id': fields.many2one(
            'hr.schedule.template',
            'Working Schedule Template',
            required=True,
        ),
    }

    def _get_sched_template(self, cr, uid, context=None):

        res = False
        init = self.get_latest_initial_values(cr, uid, context=context)
        if init is not None and init.sched_template_id:
            res = init.sched_template_id.id
        return res

    _defaults = {
        'schedule_template_id': _get_sched_template,
    }

