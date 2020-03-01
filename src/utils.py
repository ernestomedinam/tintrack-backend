from flask import jsonify, url_for
from datetime import datetime, timedelta
import re

class APIException(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)

def generate_sitemap(app):
    links = []
    for rule in app.url_map.iter_rules():
        # Filter out rules we can't navigate to in a browser
        # and rules that require parameters
        if "GET" in rule.methods and has_no_empty_params(rule):
            url = url_for(rule.endpoint, **(rule.defaults or {}))
            links.append(url)

    links_html = "".join(["<li><a href='" + y + "'>" + y + "</a></li>" for y in links])
    return """
        <div style="text-align: center;">
        <img src='https://ucarecdn.com/3a0e7d8b-25f3-4e2f-add2-016064b04075/rigobaby.jpg' />
        <h1>Hello Rigo!!</h1>
        This is your api home, remember to specify a real endpoint path like: <ul style="text-align: left;">"""+links_html+"</ul></div>"

def validate_email_syntax(email):
    email_regex = '^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$'
    if (re.search(email_regex, email)):
        # email syntax is valid
        return True
    else:
        # email syntax is not valid
        return False

def parse_tintrack_time_of_day(time_of_day):
    # check if any
    if time_of_day == "any":
        time_to_store = time_of_day
    else:
        try:
            # try parse as number of seconds from 00:00
            time_to_store = int(time_of_day)
        except ValueError:
            # try parse as time
            try:
                time_to_seconds = datetime.strptime(time_of_day, "%H:%M")
                hours_to_seconds = time_to_seconds.hour * 3600
                minutes_to_seconds = time_to_seconds.minute * 60
                time_to_store = hours_to_seconds + minutes_to_seconds
                
            except:
                print("wrong on time of day creation")
                return None
    return time_to_store

def get_date_specs(datetime_object):
    """ returns a dictionary containing:
        - datatime_object's year, month and day
        - week_number according to year_start
        - day_order and day_name according to year_start
    """
    # grab year, month and day
    year, month, day = datetime_object.year, datetime_object.month, datetime_object.day
    # grab datetime for start of year
    year_start = datetime(year=year, month=1, day=1)
    # year start was a 1(monday)-7(sunday)
    start_day_order = year_start.isoweekday()
    # this many days have passed since year started (this is a timedelta object)
    days_done = datetime_object.date() - year_start.date()
    # this many weeks have passed...
    weeks_done = days_done.days // 7
    # this means we are currently on week = weeks_done + 1
    current_week = weeks_done + 1
    # and this many days into current week
    current_days = days_done.days - weeks_done * 7

    # if year started on 1(monday)-3(wednesday), year_start happens on week 1
    # otherwise, 4(thursday)-7(sunday), year_start happens on week 0
    # first case means we are in current week, second case means we
    # actually are on week number current_week - 1
    if start_day_order > 3:
        current_week = current_week - 1
        # in this case, week 0 is a week 4...
        if current_week == 0:
            current_week = 4
    # now, if year started on anything different than 1(monday), this would mean days_done
    # did not start occurring on monday but some other day; this means that
    # current_days into current week should be modified, adding difference between
    # start_day_order and standard start day order (1-monday).
    current_days = current_days + start_day_order
    # now if current_days is > 7
    if current_days > 7:
        current_days = current_days - 7
        current_week = current_week + 1
    # now we know date_to_check is a 1(monday)-7(sunday)
    # we handle routines based on 4 week schedules, so we need a weeknumber 1-4
    while current_week > 4:
        current_week = current_week - 4

    # now we return promised dictionary
    return {
        "year": year,
        "month": month,
        "day": day,
        "week_number": current_week,
        "day_order": current_days,
        "day_name": datetime_object.strftime("%A")
    }

def list_value_to_digits(number):
    """ return a list with value number as digits """
    value_string = str(number)
    digits_list = []
    if len(value_string) == 1:
        digits_list.append(0)
    if len(value_string) > 2:
        value_string = "99"
    for digit in value_string:
        digits_list.append(int(digit))
    return digits_list

def proper_round(number, decimal=0):
    number = str(number)[:str(number).index('.') + ( decimal + 2 )]
    if number[-1] >= "5":
        integer_part = number[:-2-(not decimal)]
        decimal_part = int(number[-2-(not decimal)]) + 1
        return float(integer_part) + decimal_part ** (-decimal + 1) if integer_part and decimal_part == 10 else float(integer_part + str(decimal_part))
    return float(number[:-1])
