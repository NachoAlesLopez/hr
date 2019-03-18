# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo import api, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class HrHolidays(models.Model):
    _inherit = 'hr.holidays'

    @api.multi
    def holidays_validate(self, res_id, token):
        res = super(HrHolidays, self).holidays_validate(res_id, token)

        detail_obj = self.env['hr.schedule.detail']

        for leave in self:
            if leave.type != 'remove':
                continue

            details_to_be_removed = self.env['hr.schedule.detail']

            details = detail_obj.search([
                ('schedule_id.employee_id', '=', leave.employee_id.id),
                ('date_start', '<=', leave.date_to),
                ('date_end', '>=', leave.date_from)
            ], order='date_start')

            for detail in details:
                # Remove schedule details completely covered by leave
                if (leave.date_from <= detail.date_start
                        and leave.date_to >= detail.date_end
                        and detail not in details_to_be_removed):
                    details_to_be_removed = details_to_be_removed + detail
                # Partial day on first day of leave
                elif detail.date_start < leave.date_from <= detail.date_end:
                    dt_leave = datetime.strptime(leave.date_from,
                                                 DEFAULT_SERVER_DATETIME_FORMAT)
                    if leave.date_from == detail.date_end:
                        if detail not in details_to_be_removed:
                            details_to_be_removed.append(detail.id)
                        else:
                            dt_end = dt_leave + timedelta(seconds=-1)
                            detail.write({
                                'date_end': dt_end.strftime(
                                    DEFAULT_SERVER_DATETIME_FORMAT
                                )
                            })
                # Partial day on last day of leave
                elif detail.date_end > leave.date_to >= detail.date_start:
                    dt_leave = datetime.strptime(leave.date_to,
                                                 DEFAULT_SERVER_DATETIME_FORMAT)
                    if leave.date_to != detail.date_start:
                        dt_start = dt_leave + timedelta(seconds=+1)

                        detail.write({
                            'date_start': dt_start.strftime(
                                DEFAULT_SERVER_DATETIME_FORMAT
                            )
                        })

        details_to_be_removed.unlink()

        return res

    @api.multi
    def holidays_refuse(self, res_id, token):
        res = super(HrHolidays, self).holidays_refuse(res_id, token)

        sched_obj = self.env['hr.schedule']

        for leave in self:
            if leave.type != 'remove':
                continue

            date_leave_from = datetime.strptime(
                leave.date_from, DEFAULT_SERVER_DATETIME_FORMAT
            ).date()
            date_leave_to = datetime.strptime(
                leave.date_to, DEFAULT_SERVER_DATETIME_FORMAT
            ).date()

            schedules = sched_obj.search([
                ('employee_id', '=', leave.employee_id.id),
                ('date_start', '<=',
                 date_leave_to.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
                ('date_end', '>=',
                 date_leave_from.strftime(DEFAULT_SERVER_DATETIME_FORMAT))
            ])

            # Re-create affected schedules from scratch
            for schedule in schedules:
                schedule.delete_details()
                schedule.create_details()

        return res


