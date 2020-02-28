# tintrack REST API

tintrack is a free routine tracking application, this is it's REST API backend.

---

## how to run tintrack backend

This project is ready to run on linux ubuntu environment and uses MySql for db purposes, which you must install on your own.

Python3 is required, as well as pipenv, pkg-config python3-dev; you must also install on your own.

If you're running on Mac or Windows, just meet equivalent requirements and you should be good to go.

Once requirements are met:

- Install all of project's virtual environment packages using pipenv. Run `$ pipenv install`
- Modify .env file, generating and adding a random secret key (for request authentication purposes) and fixing your own mysql credentials, host and db name
- Create your db on mysql, i.e.: `mysql> CREATE DATABASE example;`
- Initialize your flask app db running `$ pipenv run init` (script to run `$ flask db init`)
- If no errors, migrate your db running `$ pipenv run migrate` (script to run `$ flask db migrate`)
- If all is well, upgrade to apply changed on db, running `$ pipenv run upgrade` (script to run `$ flask db upgrade`)
- Start your tintrack API running `$ pipenv run start` (script to run `$ flask run -p 8000 -h 0.0.0.0`)

If you have a gitpod account, you may try this:

[![Open in Gitpod](https://gitpod.io/button/open-in-gitpod.svg)](https://gitpod.io/from-referrer/)

---

## tintrack enpoints

### hello API

This is a simple endpoint to check if backend service is up.

id | url | methods | credentials | goal
:---: | --- | :---: | :---: | ---
1 | `/hello` | "GET" | `none` | check if API is listening

If backend service is up and running, response is:

    {"hello": "world"}, status_code = 200

### user registration

Endpoint used to create a new tintrack user based on name, email, date of birth and password.

id | url | methods | credentials | goal
:---: | --- | :---: | :---: | ---
2 | `/auth/register` | "POST" | `none` | register a new user

POST requests must include body:

    {
        "name": "user name",
        "email": "user@email.com,
        "dateOfBirth": "yyyy-mm-dd",
        "password": "Us3rP4ssw.rD"
    }

If all is ok, response is:

    {
        "result": "HTTP_201_CREATED. User Name successfully registered, log in using user@email.com"
    }, 201

Note that error responses are pretty self explanatory.

### user login

Endpoint to log in a registered user, as in checking data received for user email and password in order to create and store specific jwt credentials and that are returned as cookies for front end client to use in future requests.

id | url | methods | credentials | goal
:---: | --- | :---: | :---: | ---
3 | `/api/login` | "POST" | `none` | get authentication cookies set for a registered user based on email and password provided

If user email exists and hashed password with salt checks out, authentication cookies are provided and response is:

    {
        "result": "HTTP_200_0K. user is verified, JWT cookies set on your browser"
    },
    200

### user logout

Endpoint to end unexpired credentials validity for a user.

id | url | methods | credentials | goal
:---: | --- | :---: | :---: | ---
4 | `/api/logout` | "POST" | `HttpOnly cookie` `X-CSRF-TOKEN in header` | end current jwt tokens validity for a user

If request is valid, response is:

    {
        "result": "HTTP_200_0K. user logged out successfully"
    },
    200

### who am i?

Endpoint to provide information about credential's owner.

id | url | methods | credentials | goal
:---: | --- | :---: | :---: | ---
5 | `/api/me` | "GET" | `HttpOnly cookie` `X-CSRF-TOKEN in header` | get user information for provided credentials

If credentials are valid, response is:

    {
        "name": "User Name",
        "email": "user@email.com",
        "ranking": "starter",
        "memberSince": "yyyy-mm-dd",
        "isAuthenticated": "True"
    }

### crud habits

Endpoint to create a habit for an authenticated user.

id | url | methods | credentials | goal
:---: | --- | :---: | :---: | ---
6 | `/api/habits` | "GET" | `HttpOnly cookie` | get a list of user habits
7 | `/api/habits` | "POST" | `HttpOnly cookie` `X-CSRF-TOKEN in header` | create a habit for a user
8 | `/api/habits/<habit_id>` | "GET" |  `HttpOnly cookie` | get a specific habit information
9 | `/api/habits/<habit_id>` | "PUT" |  `HttpOnly cookie` `X-CSRF-TOKEN in header` | fully update a specific habit information
10 | `/api/habits/<habit_id>` | "DELETE" |  `HttpOnly cookie` `X-CSRF-TOKEN in header` | delete a specific habit and everything related

POST and PUT requests must include body:

    {
        "name": "Name for a habit",
        "personalMessage": "Habit's description and why user wants to quit or enforce it.",
        "targetPeriod": "daily",
        "targetValue": "12",
        "iconName": "default-habit",
        "toBeEnfoced: "true"
    }

Responses include habit objects like this:

    {
        "id": "5",
        "toBeEnforced": "True",
        "name": "Name for a habit",
        "iconName": "default-habit",
        "personalMessage" : "Habit's description and why user wants to quit or enforce it.",
        "signature": "AB87DSLJ*SF?SFKS/SFDA"
        "targetPeriod": "daily",
        "targetValues": ["1", "2"]
    }

id | status code | response body
:---: | :---: | ---
6 | `200` | a list of habit objects
7 | `201` | `"result": "HTTP_201_CREATED. habit successfully created with id: 5"`
8 | `200` | a habit object
9 | `200` | `"result": "HTTP_200_OK. habit successfully updated"`
10 | `204` | no content

### crud tasks

Endpoint to create a task for a specific user.

id | url | methods | credentials | goal
:---: | --- | :---: | :---: | ---
11 | `/api/tasks` | "GET" | `HttpOnly cookie` | get a list of user tasks
12 | `/api/tasks` | "POST" | `HttpOnly cookie` `X-CSRF-TOKEN in header` | create a task for a user
13 | `/api/tasks/<task_id>` | "GET" |  `HttpOnly cookie` | get a specific task information
14 | `/api/tasks/<task_id>` | "PUT" |  `HttpOnly cookie` `X-CSRF-TOKEN in header` | fully update a specific task information
15 | `/api/tasks/<task_id>` | "DELETE" |  `HttpOnly cookie` `X-CSRF-TOKEN in header` | delete a specific task and everything related

POST and PUT requests must include body:

    {
        "name": "Name for a task",
        "personalMessage": "Task description and why user wants to have it as part of routine.",
        "durationEstimate": "60", # in minutes
        "iconName": "default-task",
        "weekSched": [
            {
                "weekNumber": "1",
                "days": [
                    ["any"], // monday anytime
                    [], // does not happen on tuesday
                    ["any"],
                    ["36000"], // 36000 is seconds from 00:00, so this is thursday 10:00
                    ["16:00"], // friday @4pm
                    ["any", "any"], // two times, no specific hour
                    ["any", "any", "12:00", "72000"] // busy and fun...
                ]
            },
            ... other 3 weeks objects for our 4 week 28 days routine schedule.
        ]
    }

Responses include task objects like this:

    {
        "id": "5",
        "name": "Name for a task",
        "iconName": "default-task",
        "personalMessage" : "Task description and why user wants to have it as part of routine.",
        "signature": "AB87DSLJ*SF?SFKS/SFDA"
        "weekSched": [
            {
                "weekNumber": "1",
                "days": [
                    ["any"],
                    [],
                    ["any"],
                    ["36000"],
                    ["16:00"],
                    ["any", "any"],
                    ["any", "any", "12:00", "72000"]
                ]
            },
            ... other 3 weeks objects for our 4 week 28 days routine schedule.
        ]
    }

id | status code | response body
:---: | :---: | ---
11 | `200` | a list of task objects
12 | `201` | `"result": "HTTP_201_CREATED. task created successfully!"`
13 | `200` | a habit object
14 | `200` | `"result": "HTTP_200_OK. successfully updated task!"`
15 | `204` | no content

### schedules

Endpoint for an authenticated user to get his schedule for a specific date based on routine tasks and habits. Response includes a list of planned tasks and habit counter objects.

