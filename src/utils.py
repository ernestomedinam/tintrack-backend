from flask import jsonify, url_for
from datetime import datetime
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