# -*- coding: utf-8 -*-
from odoo import fields, api, models


class hr_contract(models.Model):
    _name = 'hr.contract'
    _inherit = 'hr.contract'
    
    schedule_template_id = fields.Many2one(
        comodel_name='hr.schedule.template', string='Working Schedule Template',
        required=False
    )
