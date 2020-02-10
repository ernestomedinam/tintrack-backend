"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
import os
import json
import click
from flask import Flask, request, jsonify, url_for, make_response
from flask_migrate import Migrate
from flask_swagger import swagger
from flask_cors import CORS
from utils import APIException, generate_sitemap, validate_email_syntax
from models import db, User, Habit
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token, set_access_cookies,
    get_jwt_identity, get_current_user
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
# needed for CSRF "protection"
app.config["JWT_COOKIE_CSRF_PROTECT"] = True

MIGRATE = Migrate(app, db)
db.init_app(app)
CORS(app)
jwt = JWTManager(app)

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
        if set(("name", "email", "password", "date_of_birth")).issubset(registration_data):
            # check email has valid syntax
            if validate_email_syntax(registration_data["email"]):
                # email seems fine
                new_user = User(registration_data["name"], registration_data["email"])
                # check password not empty and date_of_birth input is valid
                if new_user.set_birth_date(registration_data["date_of_birth"]) and registration_data["password"]:
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
                    # date_of_birth is not valid
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
        "is_authenticated": True
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
            new_habit_value = json.loads(new_habit_data["targetValue"])
            new_habit_icon = new_habit_data["iconName"]
            new_habit_enforcement = json.loads(new_habit_data["toBeEnforced"])
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
    auth_user = get_current_user()
    if request.method == "GET":
        pass

    elif request.method == "POST":
        pass

    elif request.method == "PUT":
        pass

    elif request.method == "DELETE":
        pass

    status_code = 501
    response_body = {
        "result": " HTTP_501_NOT_IMPLEMENTED. yet..."
    }
    return make_response (
        json.dumps(response_body),
        status_code,
        headers
    )


# this only runs if `$ python src/main.py` is executed
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=PORT, debug=False)
