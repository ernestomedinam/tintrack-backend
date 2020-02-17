from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time
import enum
import string
import os
import math
import json
import uuid
from base64 import b64encode
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from utils import parse_tintrack_time_of_day

db = SQLAlchemy()

class TargetPeriod(enum.Enum):
    DAILY = "Daily"
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"

class PlannedTaskStatus(enum.Enum):
    PENDING = "Pending"
    MISSED = "Missed"
    DONE = "Done"

class UserRanking(enum.Enum):
    STARTER = "Starter"
    ENROLLED = "Enrolled"
    EXPERIENCED = "Experienced"
    VETERAN = "Veteran"

class TinBase(db.Model):
    __abstract__ = True
    __table_args__ = {
        "mysql_engine": "InnoDB"
    }

class User(TinBase):
    """ a tintrack user. each user has a personal salt to be mixed with
        password before hashing and storing."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="J Doe")
    email = db.Column(db.String(120), unique=True, nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    password_hash = db.Column(db.String(250), nullable=False, default="default")
    user_salt = db.Column(db.String(120), nullable=False)
    ranking = db.Column(db.Enum(UserRanking), nullable=False, default="Starter")
    tasks = db.relationship("Task", backref="user", cascade="all, delete-orphan", passive_deletes=True)
    habits = db.relationship("Habit", backref="user", cascade="all, delete-orphan", passive_deletes=True)

    def __init__(self, name, email):
        if name:
            self.name = string.capwords(name)
        self.email = email.lower()
        self.user_salt = b64encode(os.urandom(32)).decode("utf-8")

    def set_password(self, password):
        """ hashes paassword and salt for user and assings to user.hash_password """
        self.password_hash = generate_password_hash(f"{password}{self.user_salt}")

    def check_password(self, password):
        """ verifies current hash_password against new password + salt hash """
        return check_password_hash(self.password_hash, f"{password}{self.user_salt}")

    def set_birth_date(self, date):
        """ parse date input and, if valid, assign to user.date_of_birth """
        try:
            self.date_of_birth = parse(date)
            # enforce age rules for user object creation
            if self.date_of_birth <= datetime.now() - relativedelta(years=18):
                return True
            else:
                return False
        except ValueError:
            return False

class TokenBlacklist(db.Model):
    """ access code tokens for users """
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False)
    token_type = db.Column(db.String(10), nullable=False)
    user_identity = db.Column(db.String(50), nullable=False)
    revoked = db.Column(db.Boolean, nullable=False)
    expires = db.Column(db.DateTime, nullable=False)
    
    def __init__(self, jti, token_type, user_identity, revoked, expires):
        self.jti = jti
        self.token_type = token_type
        self.user_identity = user_identity
        self.revoked = revoked
        self.expires = expires

    def to_dict(self):
        return {
            "token_id": self.id,
            "jti": self.jti,
            "token_type": self.token_type,
            "user_identity": self.user_identity,
            "revoked": self.revoked,
            "expires": self.expires
        }

class Activity(TinBase):
    """ an activity that has a name and a reason to be included
        in someone's routine, as a habit or a task."""
    __abstract__ = True
    name = db.Column(db.String(120), nullable=False)
    personal_message = db.Column(db.String(250), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_edited_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, name, personal_message):
        self.name = name.strip()
        self.personal_message = personal_message.strip()
        self.last_edited_at = datetime.now()

    def update(self, name, personal_message):
        self.name = name
        self.personal_message = personal_message

class Task(Activity):
    """ a task is a periodic activity that takes place in specific times
        and dates."""
    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="unique_task_for_user"),
    )
    id = db.Column(db.Integer, primary_key=True)
    duration_estimate = db.Column(db.Integer, default=0, nullable=False)
    icon_name = db.Column(db.String(50), nullable=False, default="default-task")
    signature = db.Column(db.String(100), nullable=False, default="default")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    planned_tasks = db.relationship("PlannedTask", backref="task", cascade="all, delete-orphan", passive_deletes=True)
    week_schedules = db.relationship("WeekSchedule", backref="task", cascade="all, delete-orphan", passive_deletes=True)
    kpis = db.relationship("TaskKpi", backref="task", cascade="all, delete-orphan", passive_deletes=True)

    def __init__(self, name, personal_message, duration_estimate, icon_name, user_id):
        self.duration_estimate = duration_estimate
        self.icon_name = icon_name
        self.signature = uuid.uuid4().hex
        self.user_id = user_id
        super().__init__(name, personal_message)

    @staticmethod
    def validate(json_task):
        """ validate task input and return true or false """
        weekscheds_are_valid = True
        # validate week schedule received
        if len(json_task["weekSched"]) != 4:
            # not valid if other than 4 weeks were received
            weekscheds_are_valid = False
        else:
            i = 1
            for week in json_task["weekSched"]:
                if not WeekSchedule.validate(week, i):
                    weekscheds_are_valid = False
                i += 1
        
        if (
            json_task["name"] and json_task["personalMessage"] and 
            int(json_task["durationEstimate"]) < 240 and
            json_task["iconName"] and weekscheds_are_valid
        ):
            # return valid
            
            return True
        else:
            # return invalid
            return False

    @staticmethod
    def create(json_task, user_id):
        """ create task and weekschedule objects """
        new_task = Task(
            json_task["name"], json_task["personalMessage"],
            int(json_task["durationEstimate"]), json_task["iconName"],
            user_id
        )
        db.session.add(new_task)
        try:
            db.session.commit()
        except:
            db.session.rollback()
            print("something failed in task creation")
            return None
        # task has been created, create week scheds
        for week in json_task["weekSched"]:
            # use week schedule class method for creation
            new_week_sched = WeekSchedule.create(week, new_task.id)
            if not new_week_sched:
                print("did not receive created weeksched")
                return None
        
        return new_task

    def serialize(self):
        """ return dict for task as required by front_end """
        return {
            "id": self.id,
            "name": self.name,
            "personalMessage": self.personal_message,
            "durationEstimate": self.duration_estimate,
            "iconName": self.icon_name,
            "weekSched": [week_schedule.serialize() for week_schedule in self.week_schedules]
        }

    def update(self, json_task):
        """ update task with validated input in json_task """
        self.name = json_task["name"]
        self.personal_message = json_task["personalMessage"]
        self.duration_estimate = int(json_task["durationEstimate"])
        self.icon_name = json_task["iconName"]
        self.signature = uuid.uuid4().hex
        # try:
        #     db.session.commit()
        # except:
        #     print("unexpected error saving week_sched")
        #     db.session.rollback()
        for week_sched in self.week_schedules:
            week_sched.update(json_task["weekSched"][week_sched.week_number - 1])

    def check_plan_for(self, date_to_check):
        """ checks whether planned tasks objects exist for this task
            on date_to_check based on planned tasks # vs times of day for this
            task on this date and planned_task.signature vs current task signature;
            returns true if today's planned_task are created and correspond to
            latest task signature, or if there is no planned_tasks and 
            task.times_of_day = 0; returns false otherwise """
        # grab planned tasks for this day
        planned_tasks = self.planned_tasks
        # grab times of day for this task on date_to_check
        times_of_day = self.get_times_for(date_to_check)
        # check both planned_tasks and times_of_day are not empty
        if planned_tasks != [] and times_of_day != []:
            # lists are not empty, check there are as many task.times_of_day as planned_tasks for this task
            if len(planned_tasks) == len(times_of_day):
                # same number of tasks checked, check for signature (up-to-dateness)
                if planned_tasks[0].signature == self.signature:
                    # date_to_check's plan is up to date
                    return True
                else:
                    # date_to_check's plan is obsolete
                    return False
            else:
                # number of tasks missmatch for date_to_check...
                return False
        else:
            # either no tasks are planned for this date (planned_tasks = []) or there are not
            # supposed to be any tasks planned for this date (times_of_day = [])
            if planned_tasks == [] and times_of_day == []:
                # both are empty, check_plan_for returns true
                return True
            else:
                # there is a missmatch between planned_tasks and times_of_day
                return False

    def get_times_for(self, date_to_check):
        """ returns a list with times of day for this task on received
            datetime.date(); returns empty list if no daytime objects for this date. """
        # grab year, month and day to check
        year, month, day = date_to_check.year, date_to_check.month, date_to_check.day
        # grab datetime for start of year
        year_start = datetime(year=year, month=1, day=1)
        # year start was a 1(monday)-7(sunday)
        start_day_order = year_start.isoweekday()
        # this many days have passed since year started
        days_done = date_to_check.date() - year_start.date()
        # this many weeks have passed...
        weeks_done = days_done // 7
        # this means we are currently on week = weeks_done + 1
        current_week = weeks_done + 1
        # this many days into current week
        current_days = days_done - weeks_done * 7
        # if year started on 1(monday)-3(wednesday), year_start happens on week 1
        # otherwise, 4(thursday)-7(sunday), year_start happens on week 0
        # first case means we are in current week, second case means we
        # actually are on week number current_week - 1
        if start_day_order > 3:
            current_week = current_week - 1
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
        # now we also know weeknumber, let's grab times of day
        daytime_objects = self.week_schedules[current_week - 1].weekdays[current_days - 1].daytimes
        # start times_of_day list object to return
        times_of_day = []
        if len(daytime_objects) > 0:
            for daytime in daytime_objects:
                times_of_day.append(daytime.time_of_day)
        return times_of_day

    def plan_day(self, date_to_plan, projection):
        """ deletes any planned_task for self on date_to_plan and
            creates and signs new planned_task objects for self according
            to weeksched.weekday.daytime's time_of_day and current self signature;
            returns True of False when planning (projection=False), also making changes
            on db; returns a list of planned_tasks when projecting, whithout making
            any changes to db.
        """
        # delete current planned_tasks for self on date_to_plan if planning (projection=False)
        if not projection:
            # delete planned tasks
            PlannedTask.query.filter_by(task_id=self.id, planned_date=date_to_plan.date()).delete()
        else:
            # declare list to be returned
            planned_tasks = []
        # grab times of day for date_to_plan
        times_of_day = self.get_times_for(date_to_plan)
        for time in times_of_day:
            hour = Daytime.get_hours(time)
            minute = Daytime.get_minutes(time)
            datetime_to_plan = datetime(
                year=date_to_plan.year,
                month=date_to_plan.month,
                day=date_to_plan.day,
                hour=hour,
                minute=minute
            )
            new_planned_task = PlannedTask(datetime_to_plan, self.duration_estimate, self.signature, self.id)
            if time == "any":
                new_planned_task.is_any = True
            
            # if planning, add objects to session
            if not projection:
                # add to session
                db.session.add(new_planned_task)
            else:
                # if projecting, only append to list
                planned_tasks.append(new_planned_task)
        # if planning, commit changes to db and return true/false
        if not projection:
            # commit to db

            # try to commit new planned_task objects to db
            try:
                db.session.commit()
                print("new planned tasks objects seem to have been created successfully")
                return True
            except:
                print("something went wrong when saving new planned tasks to db")
                db.session.rollback()
                return False
        else:
            # return list
            return planned_tasks

class TaskKpi(TinBase):
    """ a task key process indicators:
        current_streak: times in a row a planned task has been marked as 'done'
        longest_streak: holds highest value current_streak has ever reached for this task
    """
    id = db.Column(db.Integer, primary_key=True)
    current_streak = db.Column(db.Integer, nullable=False, default=0)
    longest_streak = db.Column(db.Integer, nullable=False, default=0)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), nullable=False)

    def __init__(self, task_id):
        self.task_id = task_id

class Habit(Activity):
    """ a habit is a recurrent activity without specific time requirements,
        usualy taking place several times per day or period. """
    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="unique_habit_for_user"),
    )
    id = db.Column(db.Integer, primary_key=True)
    to_be_enforced = db.Column(db.Boolean, nullable=False)
    target_period = db.Column(db.Enum(TargetPeriod), nullable=False)
    target_value = db.Column(db.Integer, nullable=False)
    icon_name = db.Column(db.String(50), nullable=False, default="deafult-habit")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    habit_counters = db.relationship("HabitCounter", backref="habit", cascade="all, delete-orphan", passive_deletes=True)

    def __init__(self, name, personal_message, to_be_enforced, target_period, target_value, icon_name, user_id):
        self.to_be_enforced = to_be_enforced
        self.target_period = target_period
        self.target_value = target_value
        self.icon_name = icon_name
        self.user_id = user_id
        super().__init__(name, personal_message)

    def serialize(self):
        """ return dict for habit as required by front_end """
        return {
            "id": self.id,
            "toBeEnforced": self.to_be_enforced,
            "name": self.name,
            "iconName": self.icon_name,
            "personalMessage": self.personal_message,
            "targetPeriod": self.target_period.value,
            "targetValues": self.list_target_value_digits()
        }

    def update(self, json_data):
        name = json_data["name"].strip()
        personal_message = json_data["personalMessage"].strip()
        to_be_enforced = json.loads(json_data["toBeEnforced"])
        icon_name = json_data["iconName"].strip()
        target_period = json_data["targetPeriod"].strip()
        target_value = json.loads(json_data["targetValue"])
        self.to_be_enforced = to_be_enforced
        if icon_name:
            self.icon_name = icon_name
        if target_period:
            self.target_period = target_period
        if target_value:
            self.target_value = target_value
        super().update(name, personal_message)
        
    def list_target_value_digits(self):
        """ return a list with target value digits """
        value_string = str(self.target_value)
        digits_list = []
        if len(value_string) == 1:
            digits_list.append(0)
        for digit in value_string:
            digits_list.append(int(digit))
        return digits_list

class PlannedTask(TinBase):
    """ a planned task is the ocurence, planned or as a record, of a task
        on a specific time and date, even if sometimes it is 'any'. """
    id = db.Column(db.Integer, primary_key=True)
    planned_datetime = db.Column(db.DateTime, nullable=False)
    planned_date = db.Column(db.Date, nullable=False)
    # time_of_day from task_id will settle planned_datetime on planned_task creation; if time_of_day="any"
    # then planned_datetime will be on time 00:00:00 for corresponding day; if there is already a task planned
    # for that datetime, then it will settle planned_datetime on +1 second each time. is_any=true flag is intended
    # for front end response purposes, so that we may respond "any" for planned_task start_time.
    is_any = db.Column(db.Boolean, nullable=False, default=False)
    # duration is registered in seconds
    duration_estimate = db.Column(db.Integer, nullable=False)
    registered_duration = db.Column(db.Integer)
    status = db.Column(db.Enum(PlannedTaskStatus), nullable=False, default="Pending")
    marked_done_at = db.Column(db.DateTime)
    signature = db.Column(db.String(100), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), nullable=False)
    previous_activity = db.Column(db.String(120), default="")
    as_felt_before = db.Column(db.String(120), default="")
    next_activity = db.Column(db.String(120), default="")
    as_felt_afterwards = db.Column(db.String(120), default="")

    def __init__(self, planned_datetime, duration_estimate, signature, task_id):
        self.planned_datetime = planned_datetime
        self.planned_date = planned_datetime.date()
        self.duration_estimate = duration_estimate
        self.signature = signature
        self.task_id = task_id

class HabitCounter(TinBase):
    __table_args__ = (
        db.UniqueConstraint("date_for_count", "habit_id", name="unique_date_for_habit_counter"),
    )
    id = db.Column(db.Integer, primary_key=True)
    date_for_count = db.Column(db.Date, nullable=False)
    count = db.Column(db.Integer, default=0, nullable=False)
    daily_target = db.Column(db.Integer, nullable=False)
    habit_id = db.Column(db.Integer, db.ForeignKey("habit.id", ondelete="CASCADE"), nullable=False)
    previous_activity = db.Column(db.String(120), default="")
    as_felt_before = db.Column(db.String(120), default="")
    next_activity = db.Column(db.String(120), default="")
    as_felt_afterwards = db.Column(db.String(120), default="")

    def __init__(self, date_for_count, daily_target, habit_id):
        self.date_for_count = date_for_count
        self.daily_target = daily_target
        self.habit_id = habit_id

class WeekSchedule(TinBase):
    id = db.Column(db.Integer, primary_key=True)
    week_number = db.Column(db.Integer, nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), nullable=False)
    weekdays = db.relationship("Weekday", backref="week_schedule", cascade="all, delete-orphan", passive_deletes=True)

    def __init__(self, week_number, task_id):
        self.week_number = week_number
        self.task_id = task_id

    @staticmethod
    def validate(week, week_number):
        """ validate all four weeks and its days """
        weekdays_are_valid = True
        # check days in key
        if set(("days", "weekNumber")).issubset(week):
            # now check exactly 7 days in this week days list
            if len(week["days"]) != 7 or week["weekNumber"] != week_number:
                # not valid
                weekdays_are_valid = False
            else:
                # now check each day is valid
                for day in week["days"]:
                    if not Weekday.validate(day):
                        weekdays_are_valid = False 

        else:
            # not valid, missing days key
            weekdays_are_valid = False
        
        return weekdays_are_valid

    @staticmethod
    def create(week, task_id):
        # create a week schedule for a task
        new_week_sched = WeekSchedule(int(week["weekNumber"]), task_id)
        db.session.add(new_week_sched)
        try:
            db.session.commit()
        except:
            db.session.rollback()
            print("something failed saving week sched to database")
            return None
        # create week days for this week sched
        day_number = 1
        for day in week["days"]:
            new_weekday = Weekday.create(day, day_number, new_week_sched.id)
            day_number += 1
            if not new_weekday:
                print("didnt receive created weekday")
                return None
        return new_week_sched

    def serialize(self):
        """ return a dict representation of a week schedule as
            required by front_end """
        return {
            "weekNumber": self.week_number,
            "days": [weekday.serialize() for weekday in self.weekdays]
        }

    def update(self, json_week_sched):
        """ update weekday objects for this weeksched """
        for weekday in self.weekdays:
            weekday.update(json_week_sched["days"][weekday.day_number - 1])

class Weekday(TinBase):
    id = db.Column(db.Integer, primary_key=True)
    day_number = db.Column(db.Integer, nullable=False)
    week_schedule_id = db.Column(db.Integer, db.ForeignKey("week_schedule.id", ondelete="CASCADE"), nullable=False)
    daytimes = db.relationship("Daytime", backref="weekday", cascade="all, delete-orphan", passive_deletes=True)

    def __init__(self, day_number, week_schedule_id):
        self.day_number = day_number
        self.week_schedule_id = week_schedule_id

    @staticmethod
    def validate(day):
        """ validate list of daytimes syntax """
        if len(day) > 0:
            for daytime in day:
                if daytime != "any":
                    try:
                        seconds = int(daytime)
                        if not 0 <= seconds < 24 * 3600:
                            # time received is in one day seconds range
                            return False
                    except ValueError:
                        # try parse as time
                        try:
                            new_time = datetime.strptime(daytime, "%H:%M")
                            # print(f"{new_time.hour*3600 + new_time.minute*60}")
                            if not new_time:
                                return False
                        except:
                            return False
                    
        return True

    @staticmethod
    def create(day, day_number, week_schedule_id):
        """ create a weekday and its daytime objects """
        new_weekday = Weekday(day_number, week_schedule_id)
        db.session.add(new_weekday)
        try:
            db.session.commit()
        except:
            db.session.rollback()
            print("wrong on creating weekday")
            return None
        # create daytimes
        for time_of_day in day:
            time_to_store = parse_tintrack_time_of_day(time_of_day)
            if time_to_store:
                new_time_of_day = Daytime(time_to_store, new_weekday.id)
                db.session.add(new_time_of_day)
            else:
                # something wrong with time parsing...
                return None
        try:
            db.session.commit()
        except:
            db.session.rollback()
            print("wrong on creating daytime")
            return None

        return new_weekday

    def serialize(self):
        """ return a dict representation of a weekday """
        return [daytime.serialize() for daytime in self.daytimes]

    def update(self, daytimes_list):
        Daytime.query.filter_by(weekday_id=self.id).delete()
        for time_of_day in daytimes_list:
            time_to_store = parse_tintrack_time_of_day(time_of_day)
            if time_to_store:
                new_daytime = Daytime(time_to_store, self.id)
                db.session.add(new_daytime)
            else:
                print("something went wrong parsing incoming time for day time")
                db.session.rollback()

class Daytime(TinBase):
    id = db.Column(db.Integer, primary_key=True)
    time_of_day = db.Column(db.String(10), nullable=False)
    weekday_id = db.Column(db.Integer, db.ForeignKey("weekday.id", ondelete="CASCADE"), nullable=True)

    def __init__(self, time_of_day, weekday_id):
        self.time_of_day = time_of_day
        self.weekday_id = weekday_id

    def serialize(self):
        """ return time of day as required by front_end """
        if self.time_of_day == "any":
            return self.time_of_day
        else: 
            hours = int(self.time_of_day) // 3600
            minutes = ( int(self.time_of_day) - hours * 3600 ) // 60
            time_to_return = time(hour=hours, minute=minutes)
            return time_to_return.strftime("%H:%M")

    @staticmethod
    def get_hours(time_of_day):
        """ returns time_of_day's hours """
        if time_of_day == "any":
            return 0
        else:
            return int(time_of_day) // 3600

    @staticmethod
    def get_minutes(time_of_day):
        """ returns time_of_day's minutes """
        if time_of_day == "any":
            return 0
        else:
            hours =  int(time_of_day) // 3600
            return ( int(time_of_day) - hours * 3600 ) // 60