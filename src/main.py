"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
import os
import json
import click
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify, url_for, make_response
from flask_migrate import Migrate
from flask_swagger import swagger
from flask_cors import CORS
from utils import (
    APIException, generate_sitemap, validate_email_syntax,
    get_date_specs
)
from models import db, User, Habit, Task, UserRanking, PlannedTask, HabitCounter
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token, set_access_cookies,
    get_jwt_identity, get_current_user, unset_jwt_cookies
)
from blacklist_helpers import (
    is_token_revoked, revoke_token, add_token_to_database, prune_database
)

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_CONNECTION_STRING')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# needed for encoding by flask_jwt_extended
app.config['JWT_SECRET_KEY']=os.environ.get('JWT_SECRET_KEY')
# needed for flask_jwT_extended blacklisting check
app.config["JWT_BLACKLIST_ENABLED"] = True
app.config["JWT_BLACKLIST_TOKEN_CHECKS"] = ["access"]
# needed for flask_jwt_extended cookie jwt setting
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_ACCESS_COOKIE_PATH"] = ["/api/"]
# should be true on production, demands https
app.config["JWT_COOKIE_SECURE"] = False
# fix value as desired, datetime object, deltatime object, int for seconds
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 86400
# needed for CSRF "protection"
app.config["JWT_COOKIE_CSRF_PROTECT"] = True

MIGRATE = Migrate(app, db)
db.init_app(app)
CORS(app, supports_credentials=True)
jwt = JWTManager(app)

# jwt configs
@jwt.user_claims_loader
def add_claims_to_access_token(user):
    return {
        "name": user.name
    }

@jwt.user_identity_loader
def user_identity_lookup(user):
    return user.id

@jwt.token_in_blacklist_loader
def check_if_token_revoked(decoded_token):
    return is_token_revoked(decoded_token)

@jwt.user_loader_callback_loader
def user_loader_callback(identity):
    user_from_id = User.query.filter_by(id=identity).first()
    if not user_from_id:
        return None
    return user_from_id

# Handle/serialize errors like a JSON object
@app.errorhandler(APIException)
def handle_invalid_usage(error):
    return jsonify(error.to_dict()), error.status_code

# generate sitemap with all your endpoints
@app.route('/')
def sitemap():
    return generate_sitemap(app)

@app.route('/hello', methods=['POST', 'GET'])
def handle_hello():

    response_body = {
        "hello": "world"
    }

    return jsonify(response_body), 200

# user registration endpoint
@app.route("/auth/register", methods=["POST"])
def handle_user_registration():
    headers = {
            "Content-Type": "application/json"
    }
    # check json content
    if request.json:
        # there is json content in request
        registration_data = request.json
        # check all required fields are in request data
        if set(("name", "email", "password", "dateOfBirth")).issubset(registration_data):
            # check email has valid syntax
            if validate_email_syntax(registration_data["email"]):
                # email seems fine
                new_user = User(registration_data["name"], registration_data["email"])
                # check password not empty and date_of_birth input is valid
                if new_user.set_birth_date(registration_data["dateOfBirth"]) and registration_data["password"]:
                    # user has valid birthdate and password input is not empty
                    new_user.set_password(registration_data["password"])
                    db.session.add(new_user)
                    try:
                        db.session.commit()
                        status_code = 201
                        result = f"{new_user.name} sucessfully registered, log in using {new_user.email}"
                        response_body = {
                            "result": result
                        }
                    except IntegrityError:
                        # integrity error is caused by user.email duplicate on CREATE
                        db.session.rollback()
                        status_code = 400
                        response_body = {
                            "result": "HTTP_400_BAD_REQUEST. user is trying to register again? or is it some evil toxic ex? or cops?"
                        }
                else:
                    status_code = 400
                    # date_of_birth is not valid or password came up empty
                    if registration_data["password"]:
                        response_body = {
                            "result": "HTTP_400_BAD_REQUEST. check date input, it's not valid..."
                        }
                    else:
                        response_body = {
                            "result": "HTTP_400_BAD_REQUEST. password came up empty..."
                        }
            else:
                # email syntax not valid
                status_code = 400
                response_body = {
                    "result": "HTTP_400_BAD_REQUEST. check email input, wrong syntax for email was received..."
                }
        else:
            # something came up empty
            status_code = 400
            response_body = {
                "result": "HTTP_400_BAD_REQUEST. check input, a required key is missing or was misspelled..."
            }

        
    else:
        # no json content in request...
        status_code = 400
        response_body = {
            "result": "HTTP_400_BAD_REQUEST. no json data in request... what are you trying to register?"
        }
    return make_response (
        json.dumps(response_body),
        status_code,
        headers
    )

# prune database for expired tokens
@app.cli.command("clean-expired-tokens")
def clean_expired_tokens():
    """ calls prune_database helper """
    prune_database()

# user login endpoint
@app.route("/api/login", methods=["POST"])
def handle_user_login():
    headers = {
            "Content-Type": "application/json"
    }
    # check json content
    if request.json:
        # check for data contents
        login_input = request.json
        if set(("email", "password")).issubset(login_input):
            # user input has required keys
            if login_input["email"] and login_input["password"]:
                print(f"data is {login_input['email']} {login_input['password']}")
                if validate_email_syntax(login_input["email"]):
                    # email sintax is valid
                    requesting_user = User.query.filter_by(email=login_input["email"]).first()
                    if requesting_user:
                        if requesting_user.check_password(login_input["password"]):
                            access_token = create_access_token(requesting_user)
                            add_token_to_database(access_token, app.config["JWT_IDENTITY_CLAIM"])
                            # refresh_token = create_refresh_token(requesting_user)
                            # add_token_to_database(refresh_token, app.config["JWT_IDENTITY_CLAIM"])
                            response_body = {
                                "result": "HTTP_200_0K. user is verified, JWT cookies shoulda been sent..."
                            }
                            status_code = 200
                            auth_response = make_response(
                                json.dumps(response_body),
                                status_code,
                                headers
                            )
                            set_access_cookies(auth_response, access_token)
                            return auth_response
                            
                        else:
                            status_code = 401
                            response_body = {
                                "result": "HTTP_401_UNAUTHORIZED. bad credentials..."
                            }
                    else:
                        status_code = 404
                        response_body = {
                            "result": "HTTP_401_UNAUTHORIZED. bad credentials..."
                        }
                else:
                    status_code = 400
                    response_body = {
                        "result": "HTTP_400_BAD_REQUEST. empty credentials..."
                    }
            else:
                status_code = 400
                response_body = {
                    "result": "HTTP_400_BAD_REQUEST. invalid email syntax..."
                }
        else:
            # user input is missing keys
            status_code = 400
            response_body = {
                "result": "HTTP_400_BAD_REQUEST. a key is missing or was misspelled..."
            }
    else:
        # no json content in request...
        status_code = 400
        response_body = {
            "result": "HTTP_400_BAD_REQUEST. no json data in request... what are you trying to register?"
        }
    return make_response (
        json.dumps(response_body),
        status_code,
        headers
    )

@app.route("/api/logout", methods=["POST"])
def handle_user_logout():
    headers = {
        "Content-Type": "application/json"
    }
    response_body = {
        "result": "HTTP_200_0K. user logged out successfully"
    }
    status_code = 200
    response = make_response(
        json.dumps(response_body),
        status_code,
        headers
    )
    unset_jwt_cookies(response)
    return response

# user who am i? endpoint
@app.route("/api/me", methods=["GET"])
@jwt_required
def handle_me_query():
    """ tells user (with token and csrf cookies) related identity
        data and whether he may or not use those cookies to fetch
        from API or login to refresh cookies instead """
    headers = {
        "Content-Type": "application/json"
    }
    token_user = get_current_user()
    response_body = {
        "name": token_user.name,
        "email": token_user.email,
        "ranking": token_user.ranking.value,
        "memberSince": token_user.member_since.strftime("%Y-%m-%d"),
        "isAuthenticated": True
    }
    status_code = 200
    return make_response(
        json.dumps(response_body),
        status_code,
        headers
    )

# habits endpoint
@app.route("/api/habits/", methods=["GET", "POST"])
@app.route("/api/habits/<habit_id>", methods=["GET", "PUT", "DELETE"])
@jwt_required
def handle_habits(habit_id=None):
    """ handle habits for an authenticated user """
    headers = {
        "Content-Type": "application/json"
    }
    # grab user
    auth_user = get_current_user()
    # check methods
    if request.method == "GET":
        # check if habit_id is not none
        if habit_id:
            # return specific habit details
            specific_habit = Habit.query.filter_by(id=habit_id).one_or_none()
            response_body = specific_habit.serialize()
            
        else:
            # return all user habits
            user_habits = Habit.query.filter_by(user_id=auth_user.id).all()
            response_body = []
            for habit in user_habits:
                response_body.append(habit.serialize())

        status_code = 200

    elif request.method == "POST":
        # create habit, validate input...
        new_habit_data = request.json
        if set(("name", "personalMessage", "targetPeriod", "targetValue", "iconName", "toBeEnforced")).issubset(new_habit_data):
            # all data is present
            new_habit_name = new_habit_data["name"]
            new_habit_message = new_habit_data["personalMessage"]
            new_habit_period = new_habit_data["targetPeriod"]
            new_habit_value = new_habit_data["targetValue"]
            new_habit_icon = new_habit_data["iconName"]
            new_habit_enforcement = new_habit_data["toBeEnforced"]
            if (
                new_habit_name and new_habit_message and
                new_habit_period and 0 < new_habit_value < 100 and
                new_habit_icon
            ):
                # all values valid
                new_habit = Habit(
                    new_habit_name, new_habit_message, new_habit_enforcement,
                    new_habit_period, new_habit_value, new_habit_icon, auth_user.id
                )
                
                db.session.add(new_habit)
                try:
                    db.session.commit()
                    status_code =  201
                    result = f"HTTP_201_CREATED. habit successfully created with id: {new_habit.id}"
                    response_body = {
                        "result": result
                    }
                except:
                    db.session.rollback()
                    status_code = 500
                    response_body = {
                        "result": "something went wrong in db"
                    }

            else:
                # some value is empty or invalid
                status_code = 400
                response_body = {
                    "result": "HTTP_400_BAD_REQUEST. received invalid input values..."
                }

        else:
            # some key is missing
            status_code = 400
            response_body = {
                "result": "HTTP_400_BAD_REQUEST. some key is missing in request..."
            }

    elif request.method == "PUT":
        # only allowed if habit_id is not None
        if habit_id:
            habit_to_edit = Habit.query.filter_by(id=habit_id).one_or_none()
            if habit_to_edit:
                # editing habit with input
                habit_data = request.json
                if set(("name", "personalMessage", "targetPeriod", "targetValue", "iconName", "toBeEnforced")).issubset(habit_data):
                    # all data is present
                    habit_to_edit.update(habit_data)
                    try:
                        db.session.commit()
                        status_code = 200
                        response_body = {
                            "result": "HTTP_200_OK. habit successfully updated"
                        }
                    except IntegrityError:
                        print("some error on db saving op")
                        db.session.rollback()
                        status_code = 400
                        response_body = {
                            "result": "HTTP_400_BAD_REQUEST. same user can't have two habits named the same!"
                        }

                else:
                    status_code = 400
                    response_body = {
                        "result": "HTTP_400_BAD_REQUEST. check inputs, some key is missing, this is PUT method, all keys required..."
                    }

            else:
                # oh boy, no such habit...
                status_code = 404
                response_body = {
                    "result": "HTTP_404_NOT_FOUND. oh boy, no such habit here..."
                }
        else:
            # what? no habit_id shouldn't even get in here
            status_code = 500
            response_body = {
                "result": "HTTP_666_WTF. this should not be able to happen..."
            }
            
    elif request.method == "DELETE":
        # check if habit_id and delete
        if habit_id:
            habit_to_delete = Habit.query.filter_by(id=habit_id).one_or_none()
            if habit_to_delete:
                try:
                    db.session.delete(habit_to_delete)
                    db.session.commit()
                    status_code = 204
                    response_body = {}
                except:
                    # something went wrong in db committing
                    print("dunno...")
                    status_code = 500
                    response_body = {
                        "result": "HTTP_500_INTERNAL_SERVER_ERROR. something went wrong on db..."
                    }
            else:
                # habit does not exist...
                status_code = 404
                response_body = {
                    "result": "HTTP_404_NOT_FOUND. oh boy, no such habit here..."
                }
        else:
            status_code = 500
            response_body = { 
                "result": "HTTP_666_WTF. you should not be here..."
            }
    
    return make_response (
        json.dumps(response_body),
        status_code,
        headers
    )

# tasks endpoint
@app.route("/api/tasks/", methods=["GET", "POST"])
@app.route("/api/tasks/<task_id>", methods=["GET", "PUT", "DELETE"])
@jwt_required
def handle_tasks(task_id=None):
    """ handle tasks for an authenticated user """
    headers = {
        "Content-Type": "application/json"
    }
    # grab user from request
    auth_user = get_current_user()
    if request.method == "GET":
        # check if get is for all tasks or specific task
        if task_id:
            # grab specific task
            requested_task = Task.query.filter_by(id=task_id).one_or_none()
            if requested_task:
                response_body = requested_task.serialize()
                status_code = 200
            else:
                # oh boy, no such task in here
                status_code = 404
                response_body = {
                    "result": "HTTP_404_NOT_FOUND. oh boy, no such task in here..."
                }
        
        else:
            # grab all tasks
            user_tasks = Task.query.filter_by(user_id=auth_user.id).all()
            response_body = []
            for task in user_tasks:
                response_body.append(task.serialize())
            status_code = 200

    elif request.method == "POST":
        # check data in request
        new_task_data = request.json
        
        # run class validate method to create and return new
        # object if data was valid, otherwise return none
        if set((
            "name", "personalMessage", "durationEstimate",
            "iconName", "weekSched"
        )).issubset(new_task_data):
            # use class method validator
            if Task.validate(new_task_data):
                print("data is valid and safe for task creation")
                # data is valid and safe, proceed to creation
                # use class method for creation...
                new_task = Task.create(new_task_data, auth_user.id)
                if new_task:
                    status_code = 201
                    response_body = {
                        "result": "HTTP_201_CREATED. task created successfully!"
                    }
                else:
                    status_code = 400
                    response_body = {
                        "result": "HTTP_400_BAD_REQUEST. task with same name seems to already exist"
                    }
            
            else:
                status_code = 400
                response_body = {
                    "result": "HTTP_400_BAD_REQUEST. input is not valid for task creation... check and re submit"
                }

        else: 
            # missing key
            status_code = 400
            response_body = {
                "result": "HTTP_400_BAD_REQUEST. check your keys, some is missing or was misspelled."
            }

    elif request.method == "PUT":
        # check data in request
        edit_task_data = request.json
        
        # run class validate method to create and return new
        # object if data was valid, otherwise return none
        if set((
            "name", "personalMessage", "durationEstimate",
            "iconName", "weekSched"
        )).issubset(edit_task_data):
            # check if input data is valid for task
            if Task.validate(edit_task_data):
                # data valid, check if task_id
                if task_id:
                    # check if task exists
                    task_to_edit = Task.query.filter_by(id=task_id).one_or_none()
                    if task_to_edit:
                        # task exists, validate update input
                        task_to_edit.update(edit_task_data)
                        # task_to_edit is updated, try commit()
                        try:
                            db.session.commit()
                            status_code = 200
                            response_body = {
                                "result": "HTTP_200_OK. successfully updated task!"
                            }
                        except:
                            status_code = 400
                            response_body = {
                                "result": "HTTP_400_BAD_REQUEST. name cannot be the same for two tasks!"
                            }

                    else:
                        # oh boy, no such task in here...
                        status_code = 404
                        response_body = {
                            "result": "HTTP_404_NOT_FOUND. oh boy, no such task in here..."
                        }
                
                else:
                    # there is no task_id in url!!
                    status_code = 500
                    response_body = {
                        "result": "HTTP_500_INTERNAL_SERVER_ERROR. bout to get fired, dunno how this happened..."
                    }
            else:
                # data input is not valid
                status_code = 400
                response_body = {
                    "result": "HTTP_BAD_REQUEST. data input invalid for task creation, please check..."
                }

        else:
            # some key might be missing
            status_code = 400
            response_body = {
                "result": "HTTP_400_BAD_REQUEST. check for missing or misspelled key on body..."
            }

    elif request.method == "DELETE":
        # check task_id
        if task_id:
            task_to_delete = Task.query.filter_by(id=task_id).one_or_none()
            if task_to_delete:    
                db.session.delete(task_to_delete)
                # try to commit changes to db
                try:
                    db.session.commit()
                    status_code = 204
                    response_body = {}
                except:
                    db.session.rollback()
                    print("could not delete on db")
                    status_code = 500
                    response_body = {
                        "result": "HTTP_500_INTERNAL_SERVER_ERROR. we suck at db admin..."
                    }
            else:
                status_code = 404
                response_body = {
                    "result": "HTTP_404_NOT_FOUND. oh boy, no such task in here..."
                }
        else:
            # no task id??
            status_code = 500
            response_body = {
                "result": "HTTP_500_INTERNAL_SERVER_ERROR. not supposed to happen because of flask routing..."
            }

    return make_response (
        json.dumps(response_body),
        status_code,
        headers
    )

# schedules enpoint
@app.route("/api/schedules/<requested_date>", methods=["GET"])
@app.route("/api/schedules/<requested_date>/<hours_offset>", methods=["GET"])
@jwt_required
def handle_schedule_for(requested_date, hours_offset=0):
    """ will do and return according to date:
        - if date is today: checks if today's and tomorrow's schedule 
            for requesting user are up to date; if check returns false,
            plans both days and returns today
        - if date is tomorrow: checks if today's and tomorrow's schedule 
            for requesting user are up to date; if check returns false,
            plans both days and returns tomorrow
        - if date is after tomorrow: checks requesting user's ranking
            and, if valid, projects tasks and habits on requested_date and
            returns schedule for requested_date
        - if date is before today: returns schedule for requested_date
        - if date is before user was created: returns 400   
    """
    headers = {
        "Content-Type": "application/json"
    }
    
    # grab user from request
    auth_user = get_current_user()
    # turn datetime.today() to a today valid for requesting user, based
    # on hours_offset sent in url
    utc_today = datetime.now(timezone.utc)
    hours = int(hours_offset)
    if hours < 0:
        today = utc_today - timedelta(hours=abs(hours))
    else:
        today = utc_today + timedelta(hours=abs(hours))

    # check if url requested_date is valid date input
    try:
        # input is valid
        date_to_schedule = datetime.strptime(requested_date, "%Y-%m-%d")
        
    except:
        # input invalid
        date_to_schedule = None
        print("input date is not correct")

    print(f"this is date_to_schedule {date_to_schedule}")

    if date_to_schedule:
        # check user ranking and determine days_ahead of requested_date
        # vs today
        days_ahead = date_to_schedule.date() - today.date()
        # user is valid as in user's ranking is enough to watch days_ahead
        ranking_is_enough = True
        if auth_user.ranking == UserRanking.STARTER:
            if not days_ahead.days < 1:
                # starter's ranking not enough
                ranking_is_enough = False
                response_body = {
                    "result": "more than today, until anxiety passes by, no sense for you to know it makes..."
                }
                status_code = 400

        elif auth_user.ranking == UserRanking.ENROLLED:
            if not days_ahead.days < 8:
                # enrolled's ranking not enough
                ranking_is_enough = False
                response_body = {
                    "result": "before complexity you're able to face, master a building block you must..."
                }
                status_code = 400

        elif auth_user.ranking == UserRanking.EXPERIENCED:
            if not days_ahead.days < 15:
                # experienced's ranking not enough
                ranking_is_enough = False
                response_body = {
                    "result": "a virtue, patience is; enjoyable and simple, the learning process it makes..."
                }
                status_code = 400

        elif auth_user.ranking == UserRanking.VETERAN:
            if not days_ahead.days < 29:
                # veteran's ranking not enough
                ranking_is_enough = False
                response_body = {
                    "result": "as a deceptive illusion, far future a routine master sees..."
                }
                status_code = 400

        else:
            response_body = {
                "result": "Not reading ranking right"
            }
            status_code = 203

        if ranking_is_enough:
            # check if day is today, tomorrow, past or far future
            # grab user tasks
            user_tasks = Task.query.filter_by(user_id=auth_user.id).all()
            # grab user habits
            user_habits = Habit.query.filter_by(user_id=auth_user.id).all()

            # build dahsboardDay object in response; as it's based on date_to_schedule
            # it's good for all responses
            response_body = {}
            date_specs = get_date_specs(date_to_schedule)
            response_body["year"] = date_specs["year"]
            response_body["month"] = date_specs["month"]
            response_body["day"] = date_specs["day"]
            response_body["dayName"] = date_specs["day_name"]
            response_body["dayOrder"] = date_specs["day_order"]
            response_body["weekNumber"] = date_specs["week_number"]
            response_body["plannedTasks"] = []
            response_body["habitCounters"] = []
            
            if days_ahead == timedelta(days=0) or days_ahead == timedelta(days=1):
                # date_to_schedule is today or tomorrow; check
                # both days and update if not up to date

                # for each habit now we check today's and tomorrow's counter
                for habit in user_habits:
                    habit.fix_counter_for(today)
                    habit.fix_counter_for(today + timedelta(days=1))

                # for each task now we check today's and tomorrow's plan
                for task in user_tasks:
                    if not task.check_plan_for(today):
                        # update today's plan for this task
                        print("planning for today")
                        task.plan_day(today)
                    if not task.check_plan_for(today + timedelta(days=1)):
                        # update tomorrow's plan for this task
                        print("planning for tomorrow")
                        task.plan_day(today + timedelta(days=1))

                # now, if date_to_schedule is today, we respond with
                # today's planned_tasks
                status_code = 200
                planned_tasks = []
                habit_counters = []
                if days_ahead == timedelta(days=0):    
                    # grab user habit counters for today
                    for habit in user_habits:
                        habit_counters += HabitCounter.query.filter(
                            HabitCounter.date_for_count == today.date()
                        ).filter_by(habit_id=habit.id).all()
                    # grab user planned tasks for today
                    for task in user_tasks:
                        planned_tasks += PlannedTask.query.filter(
                            PlannedTask.planned_date == today.date()
                        ).filter_by(task_id=task.id).all()
                    
                else:
                    # grab user habit counters for tomorrow
                    for habit in user_habits:
                        habit_counters += HabitCounter.query.filter(
                            HabitCounter.date_for_count == today.date() + timedelta(days=1)
                        ).filter_by(habit_id=habit.id).all()
                    # grab user planned tasks for tomorrow
                    for task in user_tasks:
                        planned_tasks += PlannedTask.query.filter(
                            PlannedTask.planned_date == today.date() + timedelta(days=1)
                        ).filter_by(task_id=task.id).all()
                
                # complete dashboardDay object in response, adding
                # planned tasks and habit counters to respond with
                today_start = datetime(year=today.year, month=today.month, day=today.day, hour=0, minute=0, second=0)
                for habit_counter in habit_counters:
                    response_body["habitCounters"].append(habit_counter.serialize())
                for planned_task in planned_tasks:
                    response_body["plannedTasks"].append(planned_task.serialize(today_start))

            elif days_ahead < timedelta(days=0):
                # date_to_schedule is a day before today; not
                # creating anything, just query and respond

                # for each habit we grab habit counters on date_to_schedule
                habit_counters = []
                for habit in user_habits:
                    habit_counters += HabitCounter.query.filter(
                        HabitCounter.date_for_count == date_to_schedule.date()
                    ).filter_by(habit_id=habit.id).all()
                # for each task we grab planned tasks on date_to_schedule
                planned_tasks = []
                for task in user_tasks:
                    planned_tasks += PlannedTask.query.filter(
                        PlannedTask.planned_date == date_to_schedule.date()
                    ).filter_by(task_id=task.id).all()
                
                # complete dashboardDay object in response, adding
                # planned tasks and habit counters to respond with
                for habit_counter in habit_counters:
                    response_body["habitCounters"].append(habit_counter.serialize())
                for planned_task in planned_tasks:
                    response_body["plannedTasks"].append(planned_task.serialize(planned_task.planned_datetime))
                status_code = 200

            else:
                # date_to_schedule is the day after tomorrow
                # not creating any planned_task, not checking,
                # only projecting...
                projected_habits = []
                for habit in user_habits:
                    projected_habits.append(habit.counter_for(date_to_schedule, True))
                projected_tasks = []
                for task in user_tasks:
                    projected_tasks += task.plan_day(date_to_schedule, True)

                # complete dashboardDay object in response, adding
                # projected tasks as planned tasks to respond with
                # and projected habit counters as counters to respond with
                today_start = datetime(year=today.year, month=today.month, day=today.day, hour=0, minute=0, second=0)
                for projected_habit in projected_habits:
                    response_body["habitCounters"].append(projected_habit.projectize(today_start))
                for projected_task in projected_tasks:
                    response_body["plannedTasks"].append(projected_task.projectize(today_start, projected_task.task_id))
                status_code = 200

    else:
        # date input in url is invalid
        response_body = {
            "result": "HTTP_404_NOT_FOUND. invalid date requested..."
        }
        status_code = 404

    return make_response (
        json.dumps(response_body),
        status_code,
        headers
    )

# this only runs if `$ python src/main.py` is executed
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=PORT, debug=False)
