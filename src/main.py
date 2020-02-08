"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
import os
import json
from flask import Flask, request, jsonify, url_for, make_response
from flask_migrate import Migrate
from flask_swagger import swagger
from flask_cors import CORS
from utils import APIException, generate_sitemap, validate_email_syntax
from models import db, User
from sqlalchemy.exc import IntegrityError
#from models import Person

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_CONNECTION_STRING')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
MIGRATE = Migrate(app, db)
db.init_app(app)
CORS(app)

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
        print(f"{registration_data}")
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

# user login endpoint
@app.route("/auth/login", methods=["POST"])
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
            pass
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

# this only runs if `$ python src/main.py` is executed
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=PORT, debug=False)
