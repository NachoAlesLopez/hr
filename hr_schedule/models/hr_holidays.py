# -*- coding: utf-8 -*-

class hr_holidays(orm.Model):

    _inherit = 'hr.holidays'

    def holidays_validate(self, cr, uid, ids, context=None):

        res = super(hr_holidays, self).holidays_validate(
            cr, uid, ids, context=context)

        if isinstance(ids, (int, long)):
            ids = [ids]

        unlink_ids = []
        det_obj = self.pool.get('hr.schedule.detail')
        for leave in self.browse(cr, uid, ids, context=context):
            if leave.type != 'remove':
                continue

            det_ids = det_obj.search(
                cr, uid, [(
                    'schedule_id.employee_id', '=', leave.employee_id.id),
                    ('date_start', '<=', leave.date_to),
                    ('date_end', '>=', leave.date_from)],
                order='date_start', context=context)
            for detail in det_obj.browse(cr, uid, det_ids, context=context):

                # Remove schedule details completely covered by leave
                if (leave.date_from <= detail.date_start
                        and leave.date_to >= detail.date_end
                        and detail.id not in unlink_ids):
                    unlink_ids.append(detail.id)

                # Partial day on first day of leave
                elif detail.date_start < leave.date_from <= detail.date_end:
                    dtLv = datetime.strptime(leave.date_from, OE_DTFORMAT)
                    if leave.date_from == detail.date_end:
                        if detail.id not in unlink_ids:
                            unlink_ids.append(detail.id)
                        else:
                            dtEnd = dtLv + timedelta(seconds=-1)
                            det_obj.write(
                                cr, uid, detail.id, {
                                    'date_end': dtEnd.strftime(OE_DTFORMAT)
                                },
                                context=context)

                # Partial day on last day of leave
                elif detail.date_end > leave.date_to >= detail.date_start:
                    dtLv = datetime.strptime(leave.date_to, OE_DTFORMAT)
                    if leave.date_to != detail.date_start:
                        dtStart = dtLv + timedelta(seconds=+1)
                        det_obj.write(
                            cr, uid, detail.id, {
                                'date_start': dtStart.strftime(OE_DTFORMAT)},
                            context=context)

        det_obj.unlink(cr, uid, unlink_ids, context=context)

        return res

    def holidays_refuse(self, cr, uid, ids, context=None):

        res = super(hr_holidays, self).holidays_refuse(
            cr, uid, ids, context=context)

        if isinstance(ids, (int, long)):
            ids = [ids]

        sched_obj = self.pool.get('hr.schedule')
        for leave in self.browse(cr, uid, ids, context=context):
            if leave.type != 'remove':
                continue

            dLvFrom = datetime.strptime(leave.date_from, OE_DTFORMAT).date()
            dLvTo = datetime.strptime(leave.date_to, OE_DTFORMAT).date()
            sched_ids = sched_obj.search(
                cr, uid, [('employee_id', '=', leave.employee_id.id),
                          ('date_start', '<=', dLvTo.strftime(
                              OE_DFORMAT)),
                          ('date_end', '>=', dLvFrom.strftime(OE_DFORMAT))])

            # Re-create affected schedules from scratch
            for sched_id in sched_ids:
                sched_obj.delete_details(cr, uid, sched_id, context=context)
                sched_obj.create_details(cr, uid, sched_id, context=context)

        return res


