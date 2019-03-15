# -*- coding: utf-8 -*-

class contract_init(orm.Model):

    _inherit = 'hr.contract.init'

    _columns = {
        'sched_template_id': fields.many2one(
            'hr.schedule.template',
            'Schedule Template',
            readonly=True,
            states={'draft': [('readonly', False)]},
        ),
    }

