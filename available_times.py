import arrow
from dateutil import tz  # For interpreting local times

import agenda

import datetime
import flask
import CONFIG
import logging


app = flask.Flask(__name__)
app.debug=CONFIG.DEBUG
app.logger.setLevel(logging.DEBUG)



def available_times(cal_list,begin_date,end_date,begin_time,end_time):
    '''
    Params:
    This function will take a calendar list of GCal events

    This function will then calculate the free times of both Gcals
    using functions stored in agenda, then return a list of free times
    '''
    app.logger.debug("cal_list: {}".format(cal_list))
    app.logger.debug("begin_date: {}".format(begin_date))
    app.logger.debug("end_date: {}".format(end_date))
    app.logger.debug("begin_time: {}".format(begin_time))
    app.logger.debug("end_time: {}".format(end_time))

    free_lists = []
    result = []
    current_agenda = agenda.Agenda()
    for i in cal_list:
        start = arrow.get(i['start']).replace(tzinfo = tz.gettz('US/Pacific'))
        day = start.date()
        end = arrow.get(i['end']).replace(tzinfo = tz.gettz('US/Pacific'))
        summary = i['summary']

        appt = agenda.Appt(day,start,end,summary)
        current_agenda.append(appt)

    #Merge overlapping events in an agenda
    current_agenda.normalize()

    a = arrow.get(begin_date)
    begin_date_time = arrow.get(begin_time).replace(year=a.year,month=a.month, day=a.day, tzinfo = tz.gettz('US/Pacific'))

    b = arrow.get(end_date)
    end_date_time = arrow.get(begin_time).replace(year=b.year,month=b.month, day=b.day, tzinfo = tz.gettz('US/Pacific'))

    for day in arrow.Arrow.range('day',start=begin_date_time, end=end_date_time):
        this_day = arrow.get(day).replace(tzinfo = tz.gettz('US/Pacific'))
        start = arrow.get(begin_time).replace(year=this_day.year,month=this_day.month,day=this_day.day,tzinfo = tz.gettz('US/Pacific'))
        end = arrow.get(end_time).replace(year=this_day.year,month=this_day.month,day=this_day.day,tzinfo = tz.gettz('US/Pacific'))

        day_freetimes = str(current_agenda.complement(agenda.Appt(this_day, start, end, 'free'))).split('\n')
        free_lists.append(day_freetimes)

    app.logger.debug("free_lists: {}".format(free_lists))
    for q in free_lists:
        for i in q:
            split = i.split('|')
            try:
                result.append({"status": 'free',"day":split[0],"start": split[1],"end":split[2]})
            except IndexError:
                    app.logger.debug("All day event removed."); #All day events display as empty list, since busy all day they are removed

    app.logger.debug("result: {}".format(result))
    return result
