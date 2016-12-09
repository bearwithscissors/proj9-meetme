import flask
from flask import render_template
from flask import request
from flask import url_for
import uuid
import time
import ast
import json
import logging

# Date handling
import arrow # Replacement for datetime, based on moment.js
# import datetime # But we still need time
from dateutil import tz  # For interpreting local times
import available_times
import agenda
import datetime


# OAuth2  - Google library implementation for convenience
from oauth2client import client
import httplib2   # used in oauth2 flow

# Google API for services
from apiclient import discovery

###
# Globals
###
import CONFIG
import secrets.admin_secrets  # Per-machine secrets
import secrets.client_secrets # Per-application secrets

# Mongo database
import pymongo
from pymongo import MongoClient
#import pymongo
# for use removing _ids
from bson.objectid import ObjectId
import secrets.admin_secrets
import secrets.client_secrets
MONGO_CLIENT_URL = "mongodb://{}:{}@localhost:{}/{}".format(
    secrets.client_secrets.db_user,
    secrets.client_secrets.db_user_pw,
    secrets.admin_secrets.port,
    secrets.client_secrets.db)

app = flask.Flask(__name__)
app.debug=CONFIG.DEBUG
app.logger.setLevel(logging.DEBUG)
app.secret_key=CONFIG.secret_key

try:
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, secrets.client_secrets.db)
    collection = db.dated

except:
    print("Failure opening database.  Is Mongo running? Correct password?")
    sys.exit(1)

SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = secrets.admin_secrets.google_key_file  ## You'll need this
APPLICATION_NAME = 'MeetMe class project'

#############################
#
#  Pages (routed from URLs)
#
#############################

@app.route("/")
@app.route("/index")
def index():
  app.logger.debug("Entering index")
  if 'begin_date' not in flask.session:
    init_session_values()
  return render_template('index.html')

@app.route("/recieved/<_id>")
def recieved(_id):
    '''
    Get database ID from sender via URL.
    Pass the ID to the DB to get the correct session values.
    '''
    app.logger.debug("Entering recieved")
    flask.session["recipient_id"] = _id
    recieved_db = dict(collection.find( { "_id": ObjectId(_id) } )[0])
    flask.session["sender"] = recieved_db["sender"]
    flask.session["sender_email"] = recieved_db["sender_email"]
    flask.session["recipient"] = recieved_db["recipient"]
    flask.session["recipient_email"] = recieved_db["recipient_email"]
    flask.session["sender_freetimes"] = recieved_db["sender_freetimes"]
    flask.session["sent_begin_time"] = recieved_db["sent_begin_time"]
    flask.session["sent_end_time"] = recieved_db["sent_end_time"]
    flask.session["begin_date"] = recieved_db["begin_date"]
    flask.session["end_date"] = recieved_db["end_date"]
    flask.session["sender_busy_times"] = recieved_db["sender_busy_times"]
    return render_template('recieved.html')

@app.route("/choose")
def choose():
    ## We'll need authorization to list calendars
    ## I wanted to put what follows into a function, but had
    ## to pull it back here because the redirect has to be a
    ## 'return'
    flask.session['primary_cals'] = []
    app.logger.debug("Checking credentials for Google calendar access")
    credentials = valid_credentials()
    if not credentials:
      app.logger.debug("Redirecting to authorization")
      return flask.redirect(flask.url_for('oauth2callback'))

    gcal_service = get_gcal_service(credentials)
    app.logger.debug("Returned from get_gcal_service")
    flask.g.calendars = list_calendars(gcal_service)
    if 'sender_freetimes' in flask.session:
        return render_template('recieved.html')
    return render_template('index.html')

@app.route("/list_chosen")
def list_chosen():
    flask.session['for_mongo'] = []
    result = []
    loops = 0
    cal_ids = flask.session['primary_cals']
    for i in range(len(cal_ids)):
        loops += 1
        app.logger.debug("Checking credentials for Google calendar access")
        credentials = valid_credentials()
        if not credentials:
          app.logger.debug("Redirecting to authorization")
          return flask.redirect(flask.url_for('oauth2callback'))

        gcal_service = get_gcal_service(credentials)
        eventsResult = gcal_service.events().list(
            calendarId=flask.session['primary_cals'][i], timeMin=flask.session["begin_date_time"], timeMax=flask.session["end_date_time"],maxResults=100, singleEvents=True,
            orderBy='startTime').execute()
        events = eventsResult.get('items', [])


        if not events:
            app.logger.debug("no upcomming events found")
        for event in events:
            summary = event['summary']
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))


            result.append(
              { #"id": id
                "summary": summary,
                "start": start,
                "end": end,
                })

    result = sorted(result, key=lambda k: k['start'])
    if 'sender_freetimes' not in flask.session:
        flask.session["sender_busy_times"] = result
    else:
        for date in flask.session['sender_busy_times']:
            result.append(date)
    free_times = available_times.available_times(result,flask.session["begin_date_time"],flask.session["end_date_time"],flask.session["begin_time"],flask.session["end_time"])
    flask.g.cal_list = free_times
    if 'sender_freetimes' in flask.session:
        return render_template('recieved.html')
    return render_template('index.html')

@app.route("/_add_primary")
def add_primary():
    id = request.args.get('id', 0, type=str)
    for i in flask.session['query_cal']:
        if i.get('id') == id:
            new_id = str(i.get('id'))
            flask.session["primary_cals"].append(new_id)

    #app.logger.debug("primary_cals{}".format(flask.session['primary_cals']))
    if 'sender_freetimes' in flask.session:
            return render_template('recieved.html')
    return render_template('index.html')

@app.route("/_add_free")
def add_free():
    '''
    add free times from radiobutton, also has implementation for
    checkboxes in the sender form. (to be continued)
    '''
    free = request.args.get('free', 0, type=str)
    if 'sender_freetimes' in flask.session:
        if 'radio_choice' not in flask.session:
            flask.session["radio_choice"] = {}
        flask.session["radio_choice"] = ast.literal_eval(free)
        app.logger.debug("radio_choice: {}".format(flask.session['radio_choice']))
    else:
        if 'for_mongo' not in flask.session:
            flask.session['for_mongo'] = []
        flask.session["for_mongo"].append(free)
        app.logger.debug("added to for_mongo: {}".format(flask.session['for_mongo']))

    if 'sender_freetimes' in flask.session:
            return render_template('recieved.html')
    return render_template('index.html')

@app.route("/_remove_free")
def remove_free():
    '''
    removes free times from radiobuttons, also has implementation for
    checkboxes in the sender form. (to be continued)
    '''
    free = request.args.get('free', 0, type=str)
    if 'sender_freetimes' in flask.session:
        #flask.session["radio_choice"].remove(free)
        app.logger.debug("removed from radio: {}".format(flask.session['radio_choice']))
    else:
        flask.session["for_mongo"].remove(free)
        app.logger.debug("removed from for_mongo: {}".format(flask.session['for_mongo']))

    if 'sender_freetimes' in flask.session:
            return render_template('recieved.html')
    return render_template('index.html')

@app.route("/_remove_primary")
def remove_primary():
    id = request.args.get('id', 0, type=str)
    app.logger.debug("primary_cals{}".format(flask.session['primary_cals']))
    for i in flask.session['query_cal']:
        if i.get('id') == id:
            new_id = str(i.get('id'))
            flask.session["primary_cals"].remove(new_id)

    #app.logger.debug("primary_cals{}".format(flask.session['primary_cals']))
    if 'sender_freetimes' in flask.session:
            return render_template('recieved.html')
    return render_template('index.html')

@app.route("/_create_entry")
def create_entry():
    entry = {
    "type":"freetime",
    "sender":flask.session["sender"],
    "sender_email":flask.session["sender_email"],
    "sender_freetimes":flask.session["for_mongo"],
    "recipient":flask.session["recipient"],
    "recipient_email":flask.session["recipient_email"],
    "sent_begin_time":flask.session["begin_time"],
    "sent_end_time":flask.session["end_time"],
    "begin_date":flask.session["begin_date"],
    "end_date":flask.session["end_date"],
    "sender_busy_times":flask.session["sender_busy_times"]
    }
    collection.insert(entry)

    flask.session["recipient_id"] = str(collection.find(entry)[0]['_id'])

    app.logger.debug("db: {}".format(str(flask.session['recipient_id'])))
    app.logger.debug("entry: {}".format(str(entry)))

    return render_template('done.html')


####
#
#  Google calendar authorization:
#      Returns us to the main /choose screen after inserting
#      the calendar_service object in the session state.  May
#      redirect to OAuth server first, and may take multiple
#      trips through the oauth2 callback function.
#
#  Protocol for use ON EACH REQUEST:
#     First, check for valid credentials
#     If we don't have valid credentials
#         Get credentials (jump to the oauth2 protocol)
#         (redirects back to /choose, this time with credentials)
#     If we do have valid credentials
#         Get the service object
#
#  The final result of successful authorization is a 'service'
#  object.  We use a 'service' object to actually retrieve data
#  from the Google services. Service objects are NOT serializable ---
#  we can't stash one in a cookie.  Instead, on each request we
#  get a fresh serivce object from our credentials, which are
#  serializable.
#
#  Note that after authorization we always redirect to /choose;
#  If this is unsatisfactory, we'll need a session variable to use
#  as a 'continuation' or 'return address' to use instead.
#
####


def valid_credentials():
    """
    Returns OAuth2 credentials if we have valid
    credentials in the session.  This is a 'truthy' value.
    Return None if we don't have credentials, or if they
    have expired or are otherwise invalid.  This is a 'falsy' value.
    """
    if 'credentials' not in flask.session:
      return None

    credentials = client.OAuth2Credentials.from_json(
        flask.session['credentials'])

    if (credentials.invalid or
        credentials.access_token_expired):
      return None
    return credentials


def get_gcal_service(credentials):
  """
  We need a Google calendar 'service' object to obtain
  list of calendars, busy times, etc.  This requires
  authorization. If authorization is already in effect,
  we'll just return with the authorization. Otherwise,
  control flow will be interrupted by authorization, and we'll
  end up redirected back to /choose *without a service object*.
  Then the second call will succeed without additional authorization.
  """
  app.logger.debug("Entering get_gcal_service")
  http_auth = credentials.authorize(httplib2.Http())
  service = discovery.build('calendar', 'v3', http=http_auth)
  app.logger.debug("Returning service")
  return service

@app.route('/oauth2callback')
def oauth2callback():
  """
  The 'flow' has this one place to call back to.  We'll enter here
  more than once as steps in the flow are completed, and need to keep
  track of how far we've gotten. The first time we'll do the first
  step, the second time we'll skip the first step and do the second,
  and so on.
  """
  app.logger.debug("Entering oauth2callback")
  flow =  client.flow_from_clientsecrets(
      CLIENT_SECRET_FILE,
      scope= SCOPES,
      redirect_uri=flask.url_for('oauth2callback', _external=True))
  ## Note we are *not* redirecting above.  We are noting *where*
  ## we will redirect to, which is this function.

  ## The *second* time we enter here, it's a callback
  ## with 'code' set in the URL parameter.  If we don't
  ## see that, it must be the first time through, so we
  ## need to do step 1.
  app.logger.debug("Got flow")
  if 'code' not in flask.request.args:
    app.logger.debug("Code not in flask.request.args")
    auth_uri = flow.step1_get_authorize_url()
    return flask.redirect(auth_uri)
    ## This will redirect back here, but the second time through
    ## we'll have the 'code' parameter set
  else:
    ## It's the second time through ... we can tell because
    ## we got the 'code' argument in the URL.
    app.logger.debug("Code was in flask.request.args")
    auth_code = flask.request.args.get('code')
    credentials = flow.step2_exchange(auth_code)
    flask.session['credentials'] = credentials.to_json()
    ## Now I can build the service and execute the query,
    ## but for the moment I'll just log it and go back to
    ## the main screen
    app.logger.debug("Got credentials")
    return flask.redirect(flask.url_for('choose'))

#####
#
#  Option setting:  Buttons or forms that add some
#     information into session state.  Don't do the
#     computation here; use of the information might
#     depend on what other information we have.
#   Setting an option sends us back to the main display
#      page, where we may put the new information to use.
#
#####

@app.route('/setrange', methods=['POST'])
def setrange():
    """
    User chose a date range with the bootstrap daterange
    widget.
    """
    app.logger.debug("Entering setrange")
    flask.flash("Setrange gave us '{}'".format(
      request.form.get('daterange')))
    daterange = request.form.get('daterange')
    begin_time = request.form.get('begin_time')
    flask.session['begin_time'] = interpret_time(begin_time)
    end_time = request.form.get('end_time')
    flask.session['end_time'] = interpret_time(end_time)
    flask.session['daterange'] = daterange
    daterange_parts = daterange.split()
    flask.session['begin_date'] = interpret_date(daterange_parts[0])
    flask.session['end_date'] = interpret_date(daterange_parts[2])
    app.logger.debug("Setrange parsed {} - {}  dates as {} - {}".format(
      daterange_parts[0], daterange_parts[1],
      flask.session['begin_date'], flask.session['end_date']))

    a = arrow.get(flask.session['begin_date'])
    begin_date_time = arrow.get(flask.session['begin_time'])
    begin_date_time = begin_date_time.replace(year=a.year,month=a.month, day=a.day)
    flask.session['begin_date_time'] = begin_date_time.isoformat()

    b = arrow.get(flask.session['end_date'])
    end_date_time = arrow.get(flask.session['end_time'])
    end_date_time = end_date_time.replace(year=b.year,month=b.month, day=b.day)
    flask.session['end_date_time'] = end_date_time.isoformat()
    flask.session['for_mongo'] = []
    flask.session['sender'] = request.form.get('sender_name')
    flask.session['sender_email'] = request.form.get('sender_email')
    flask.session['recipient'] = request.form.get('recipient_name')
    flask.session['recipient_email'] = request.form.get('recipient_email')


    return flask.redirect(flask.url_for("choose"))

@app.route('/set_recieved_range', methods=['POST'])
def set_recieved_range():
    """
    User chose a date range with the bootstrap daterange
    widget.
    """
    app.logger.debug("Entering setrange")
    flask.flash("Setrange gave us '{}'".format(
      request.form.get('daterange')))
    #daterange = request.form.get('daterange')
    begin_time = request.form.get('begin_time')
    flask.session['begin_time'] = interpret_time(begin_time)
    end_time = request.form.get('end_time')
    flask.session['end_time'] = interpret_time(end_time)
    #flask.session['daterange'] = daterange
    #daterange_parts = daterange.split()

    #app.logger.debug("Setrange parsed {} - {}  dates as {} - {}".format(
      #daterange_parts[0], daterange_parts[1],
      #flask.session['begin_date'], flask.session['end_date']))

    a = arrow.get(flask.session['begin_date'])
    begin_date_time = arrow.get(flask.session['begin_time'])
    begin_date_time = begin_date_time.replace(year=a.year,month=a.month, day=a.day)
    flask.session['begin_date_time'] = begin_date_time.isoformat()

    b = arrow.get(flask.session['end_date'])
    end_date_time = arrow.get(flask.session['end_time'])
    end_date_time = end_date_time.replace(year=b.year,month=b.month, day=b.day)
    flask.session['end_date_time'] = end_date_time.isoformat()

    return flask.redirect(flask.url_for("choose"))

@app.route('/recieved_decided')
def recieved_decided():
    '''
    Recieve radio button date value,
    Add to mongodb database,

    Load new page with sender's name, and email from mongodb
    '''
    flask.session["final_day"] = flask.session["radio_choice"].get("day")
    flask.session["final_start"] = flask.session["radio_choice"].get("start")
    flask.session["final_end"] = flask.session["radio_choice"].get("end")
    return render_template('done.html')



####
#
#   Initialize session variables
#
####

def init_session_values():
    """
    Start with some reasonable defaults for date and time ranges.
    Note this must be run in app context ... can't call from main.
    """
    # Default date span = tomorrow to 1 week from now
    now = arrow.now('local')     # We really should be using tz from browser
    tomorrow = now.replace(days=+1)
    nextweek = now.replace(days=+7)

    flask.session["begin_date"] = tomorrow.floor('day').isoformat()
    flask.session["end_date"] = nextweek.ceil('day').isoformat()
    flask.session["daterange"] = "{} - {}".format(
        tomorrow.format("MM/DD/YYYY"),
        nextweek.format("MM/DD/YYYY"))
    # Default time span each day, 8 to 5
    flask.session["begin_time"] = interpret_time("10am")
    flask.session["end_time"] = interpret_time("5pm")
    flask.session["primary_cals"] = []
    flask.session['for_mongo'] = []


def interpret_time( text ):
    """
    Read time in a human-compatible format and
    interpret as ISO format with local timezone.
    May throw exception if time can't be interpreted. In that
    case it will also flash a message explaining accepted formats.
    """
    app.logger.debug("Decoding time '{}'".format(text))
    time_formats = ["ha", "h:mma",  "h:mm a", "H:mm"]
    try:
        as_arrow = arrow.get(text, time_formats).replace(tzinfo=tz.tzlocal())
        as_arrow = as_arrow.replace(year=2016) #HACK see below
        app.logger.debug("Succeeded interpreting time")
    except:
        app.logger.debug("Failed to interpret time")
        flask.flash("Time '{}' didn't match accepted formats 13:30 or 1:30pm"
              .format(text))
        raise
    return as_arrow.isoformat()
    #HACK #Workaround
    # isoformat() on raspberry Pi does not work for some dates
    # far from now.  It will fail with an overflow from time stamp out
    # of range while checking for daylight savings time.  Workaround is
    # to force the date-time combination into the year 2016, which seems to
    # get the timestamp into a reasonable range. This workaround should be
    # removed when Arrow or Dateutil.tz is fixed.
    # FIXME: Remove the workaround when arrow is fixed (but only after testing
    # on raspberry Pi --- failure is likely due to 32-bit integers on that platform)


def interpret_date( text ):
    """
    Convert text of date to ISO format used internally,
    with the local time zone.
    """
    try:
      as_arrow = arrow.get(text, "MM/DD/YYYY").replace(
          tzinfo=tz.tzlocal())
    except:
        flask.flash("Date '{}' didn't fit expected format 12/31/2001")
        raise
    return as_arrow.isoformat()

def next_day(isotext):
    """
    ISO date + 1 day (used in query to Google calendar)
    """
    as_arrow = arrow.get(isotext)
    return as_arrow.replace(days=+1).isoformat()

####
#
#  Functions (NOT pages) that return some information
#
####

def list_calendars(service):
    """
    Given a google 'service' object, return a list of
    calendars.  Each calendar is represented by a dict.
    The returned list is sorted to have
    the primary calendar first, and selected (that is, displayed in
    Google Calendars web app) calendars before unselected calendars.
    """
    app.logger.debug("Entering list_calendars")
    calendar_list = service.calendarList().list().execute()["items"]
    result = [ ]
    query_cal = [ ]
    for cal in calendar_list:
        kind = cal["kind"]
        id = cal["id"]
        if "description" in cal:
            desc = cal["description"]
        else:
            desc = "(no description)"
        summary = cal["summary"]
        # Optional binary attributes with False as default
        selected = ("selected" in cal) and cal["selected"]
        primary = ("primary" in cal) and cal["primary"]


        result.append(
          { "kind": kind,
            "id": id,
            "summary": summary,
            "selected": selected,
            "primary": primary
            })

        query_cal.append({ "id" : id })

    flask.session['query_cal'] = query_cal
    return sorted(result, key=cal_sort_key)



def cal_sort_key( cal ):
    """
    Sort key for the list of calendars:  primary calendar first,
    then other selected calendars, then unselected calendars.
    (" " sorts before "X", and tuples are compared piecewise)
    """
    if cal["selected"]:
       selected_key = " "
    else:
       selected_key = "X"
    if cal["primary"]:
       primary_key = " "
    else:
       primary_key = "X"
    return (primary_key, selected_key, cal["summary"])


#################
#
# Functions used within the templates
#
#################

@app.template_filter( 'fmtdate' )
def format_arrow_date( date ):
    try:
        normal = arrow.get( date )
        return normal.format("ddd MM/DD/YYYY")
    except:
        return "(bad date)"

@app.template_filter( 'fmttime' )
def format_arrow_time( time ):
    try:
        normal = arrow.get( time )
        return normal.format("HH:mm")
    except:
        return "(bad time)"

#############


if __name__ == "__main__":
  # App is created above so that it will
  # exist whether this is 'main' or not
  # (e.g., if we are running under green unicorn)
  app.run(port=CONFIG.PORT,host="0.0.0.0")
