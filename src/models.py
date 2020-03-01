from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time, timedelta, timezone
import enum
import string
import os
import math
import json
import uuid
from base64 import b64encode
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from utils import (
    parse_tintrack_time_of_day, get_date_specs, list_value_to_digits,
    proper_round
)

db = SQLAlchemy()


class TargetPeriod(enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class PlannedTaskStatus(enum.Enum):
    PENDING = "pending"
    DONE = "done"


class UserRanking(enum.Enum):
    STARTER = "starter"
    ENROLLED = "enrolled"
    EXPERIENCED = "experienced"
    VETERAN = "veteran"


class CountStatus(enum.Enum):
    UNDER = "under"
    AROUND = "around"
    OVER = "over"


class Feeling(enum.Enum):
    SADDER = 1
    SAD = 2
    INDIFFERENT = 3
    HAPPY = 4
    HAPPIER = 5


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
    ranking = db.Column(db.Enum(UserRanking), nullable=False, default="starter")
    member_since = db.Column(db.DateTime, nullable=False, default="")
    tasks = db.relationship("Task", backref="user", cascade="all, delete-orphan", passive_deletes=True)
    habits = db.relationship("Habit", backref="user", cascade="all, delete-orphan", passive_deletes=True)

    def __init__(self, name, email):
        if name:
            self.name = string.capwords(name)
        self.email = email.lower()
        self.member_since = datetime.now(timezone.utc)
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
    signature = db.Column(db.String(100), nullable=False, default="default")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_edited_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, name, personal_message):
        self.name = name.strip()
        self.personal_message = personal_message.strip()
        self.last_edited_at = datetime.now(timezone.utc)
        self.signature = uuid.uuid4().hex

    def update(self, name, personal_message):
        self.name = name
        self.personal_message = personal_message
        self.signature = uuid.uuid4().hex
        self.last_edited_at = datetime.now(timezone.utc)


class Task(Activity):
    """ a task is a periodic activity that takes place in specific times
        and dates."""
    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="unique_task_for_user"),
    )
    id = db.Column(db.Integer, primary_key=True)
    duration_estimate = db.Column(db.Integer, default=0, nullable=False)
    icon_name = db.Column(db.String(50), nullable=False, default="default-task")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    planned_tasks = db.relationship("PlannedTask", backref="task", cascade="all, delete-orphan", passive_deletes=True)
    week_schedules = db.relationship("WeekSchedule", backref="task", cascade="all, delete-orphan", passive_deletes=True)
    kpi = db.relationship("TaskKpi", backref="task", cascade="all, delete-orphan", passive_deletes=True, uselist=False)

    def __init__(self, name, personal_message, duration_estimate, icon_name, user_id):
        self.duration_estimate = duration_estimate
        self.icon_name = icon_name
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
        # create kpi object
        new_kpi_object = TaskKpi(new_task.id)
        db.session.add(new_kpi_object)
        try:
            db.session.commit()
        except:
            print("something failed creating task_kpi")
            db.session.rollback()
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
            "signature": self.signature,
            "weekSched": [week_schedule.serialize() for week_schedule in self.week_schedules]
        }

    def update(self, json_task):
        """ update task with validated input in json_task """
        self.duration_estimate = int(json_task["durationEstimate"])
        self.icon_name = json_task["iconName"]
        for week_sched in self.week_schedules:
            week_sched.update(json_task["weekSched"][week_sched.week_number - 1])
        super().update(json_task["name"], json_task["personalMessage"])

    def check_plan_for(self, date_to_check):
        """ checks whether planned tasks objects exist for this task
            on date_to_check based on planned tasks # vs times of day for this
            task on this date and planned_task.signature vs current task signature;
            returns true if today's planned_task are created and correspond to
            latest task signature, or if there is no planned_tasks and 
            task.times_of_day = 0; returns false otherwise """
        # grab planned tasks for this day and this task!
        planned_tasks = PlannedTask.query.filter_by(planned_date=date_to_check.date()).filter_by(task_id=self.id).all()
        # grab times of day for this task on date_to_check
        times_of_day = self.get_times_for(date_to_check)
        # check both planned_tasks and times_of_day are not empty
        if planned_tasks != [] and times_of_day != []:
            # lists are not empty, check there are as many task.times_of_day as planned_tasks for this task
            if len(planned_tasks) == len(times_of_day):
                # same number of tasks checked, check for signature (up-to-dateness)
                if planned_tasks[0].signature == self.signature:
                    # date_to_check's plan is up to date
                    # print("up to date")
                    return True
                else:
                    # date_to_check's plan is obsolete
                    # print("signature missmatch")
                    return False
            else:
                # number of tasks missmatch for date_to_check...
                # print("amount missmatch")
                return False
        else:
            # either no tasks are planned for this date (planned_tasks = []) or there are not
            # supposed to be any tasks planned for this date (times_of_day = [])
            if planned_tasks == [] and times_of_day == []:
                # both are empty, check_plan_for returns true
                # print("up to date, no planned tasks")
                return True
            else:
                # there is a missmatch between planned_tasks and times_of_day
                # print("one is cero, amount missmatch")
                return False

    def get_times_for(self, date_to_check):
        """ returns a list with times of day for this task on received
            datetime.date(); returns empty list if no daytime objects for this date.
        """

        # get week_number and day_order from date_to_check
        date_specs = get_date_specs(date_to_check)
        week_number = int(date_specs["week_number"]) - 1
        day_order = int(date_specs["day_order"]) - 1
        
        # now we know week_number and day_order, let's grab times of day
        daytime_objects = self.week_schedules[week_number].weekdays[day_order].daytimes
        # start times_of_day list object to return
        times_of_day = []
        if len(daytime_objects) > 0:
            for daytime in daytime_objects:
                times_of_day.append(daytime.time_of_day)
        return times_of_day

    def plan_day(self, date_to_plan, projection=False):
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
                return True
            except:
                db.session.rollback()
                return False
        else:
            # return list
            return planned_tasks

    def get_kpis_for(self, datetime_object):
        """ returns a list of dictionaries with:
            - current_streak: times in a row a planned task is done in a list of
                planned tasks with planned_datetime < datetime_object, ordered from
                present to past
            - longest_streak: as recorded on task_kpi object
            - average: times planned tasks are done over all of them, in % format
        """
        current_streak = self.get_streak_up_to(datetime_object)
        longest_streak = self.kpi.longest_streak
        average = self.get_average_up_to(datetime_object)
        return [
            {
                "legend": "streak",
                "numbers":  list_value_to_digits(current_streak)
            },
            {
                "legend": "longest",
                "numbers": list_value_to_digits(longest_streak)
            },
            {
                "legend": "avg %",
                "numbers": list_value_to_digits(average)
            }
        ]
        
    def get_streak_up_to(self, datetime_object):
        """" returns times in a row a planned task was done from datetime_object to the past """
        planned_tasks = PlannedTask.query.filter(
            PlannedTask.planned_datetime <= datetime_object
        ).filter_by(task_id=self.id).order_by(PlannedTask.planned_datetime.desc()).all()
        # check if task is done and add to streak
        streak = 0
        for planned_task in planned_tasks:
            # print(f"{planned_task.task.name} {planned_task.planned_datetime} {planned_task.status}")
            if planned_task.status == PlannedTaskStatus.DONE:
                streak += 1
            else:
                break
        return streak

    def get_average_up_to(self, datetime_object):
        """ returns average done/all from datetime_object to the past """
        done_planned_tasks = PlannedTask.query.filter(
            db.and_(
                PlannedTask.planned_datetime <= datetime_object,
                PlannedTask.status == PlannedTaskStatus.DONE
            )
        ).filter_by(task_id=self.id).all()
        planned_tasks = PlannedTask.query.all()
        current_average = len(done_planned_tasks) / len(planned_tasks)
        return int(100 * current_average) 


class TaskKpi(TinBase):
    """ a task key process indicators:
        current_streak: times in a row a planned task has been marked as 'done'
        longest_streak: holds highest value current_streak has ever reached for this task
    """
    id = db.Column(db.Integer, primary_key=True)
    longest_streak = db.Column(db.Integer, nullable=False, default=0)
    best_average = db.Column(db.Float, nullable=False, default=0)
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
            "signature": self.signature,
            "targetPeriod": self.target_period.value,
            "targetValues": self.list_target_value_digits()
        }

    def update(self, json_data):
        name = json_data["name"].strip()
        personal_message = json_data["personalMessage"].strip()
        to_be_enforced = json_data["toBeEnforced"]
        icon_name = json_data["iconName"].strip()
        target_period = json_data["targetPeriod"].strip()
        target_value = json_data["targetValue"]
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

    def fix_counter_for(self, date_to_check):
        """ works out habit counter situation for this habit, meaning that
            if it does not exist for date_to_check it gets created; if it
            exists but is out of date (signature missmatch) it gets updated.
            this method should only be used on date_to_check >= today...
        """
        # grab habit counter for this habit on date_to_check
        habit_counter = HabitCounter.query.filter(
            HabitCounter.date_for_count == date_to_check.date()
        ).filter_by(habit_id=self.id).one_or_none()
        if not habit_counter:
            # if habit_counter does not exist, it is created
            habit_counter = self.counter_for(date_to_check)

        else:
            # otherwise, it is checked
            if not habit_counter.signature == self.signature:
                # habit counter is not up to date
                habit_counter.sign_latest()
        
        return habit_counter

    def counter_for(self, date_to_plan, projection=False):
        """ creates and commits to db a new habit_counter object;
            when projection True, returns object wihtout commiting to db
        """
        # create new habit counter
        new_habit_counter = HabitCounter(
            date_to_plan, self.get_daily_target(),
            self.signature, self.id
        )

        if not projection:
            # try to commit created habit_counter
            db.session.add(new_habit_counter)
            try:
                db.session.commit()
                return new_habit_counter
            except:
                db.session.rollback()
                print("something went wrong when commiting new habit counter")
                return None
        else:
            return new_habit_counter

    def get_daily_target(self):
        """ return a float value that represents daily target based on 
            target_period and target_value. this methos is used to store
            daily_target for habit_counters.
        """
        # check self.target_period
        if self.target_period == TargetPeriod.MONTHLY:
            # fix daily target accordingly
            target = self.target_value / 28
        elif self.target_period == TargetPeriod.WEEKLY:
            # fix daily turning week to day
            target = self.target_value / 7
        else:
            # it's daily
            target = self.target_value

        return target


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
    registered_duration = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.Enum(PlannedTaskStatus), nullable=False, default="pending")
    marked_done_at = db.Column(db.DateTime)
    signature = db.Column(db.String(100), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), nullable=False)
    # previous_activity = db.Column(db.String(120), default="")
    # as_felt_before = db.Column(db.String(120), default="")
    #next_activity = db.Column(db.String(120), default="")
    # as_felt_afterwards = db.Column(db.String(120), default="")

    def __init__(self, planned_datetime, duration_estimate, signature, task_id):
        self.planned_datetime = planned_datetime
        self.planned_date = planned_datetime.date()
        self.duration_estimate = duration_estimate
        self.signature = signature
        self.task_id = task_id
    
    def projectize(self, kpi_datetime, task_id):
        """ return a projected task dict as expected by fron end client
            mimics serialize and adds things that would only be available
            for planned_task object after db commit().
        """
        task = Task.query.filter_by(id=task_id).one_or_none()
        if task:
            if self.is_any:
                is_any = self.is_any
            else:
                is_any = False

            return {
                "id": uuid.uuid4().hex,
                "startTime": self.planned_datetime.strftime("%H:%M"),
                "durationEstimate": self.duration_estimate,
                "status": PlannedTaskStatus.PENDING.value,
                "name": task.name,
                "iconName": task.icon_name,
                "personalMessage": task.personal_message,
                "duration": 0,
                "signature": self.signature,
                "isAny": is_any,
                "kpiValues": task.get_kpis_for(kpi_datetime)
            }
        else:
            print("shit, something is wrong with that task_id")
            return {
                "a problem": "there is"
            }
        
    def serialize(self, kpi_datetime):
        """ return a planned task dict as expected by front end client """
        return {
            "id": self.id,
            "startTime": self.planned_datetime.strftime("%H:%M"),
            "durationEstimate": self.duration_estimate,
            "status": self.status.value,
            "name": self.task.name,
            "iconName": self.task.icon_name,
            "personalMessage": self.task.personal_message,
            "duration": self.registered_duration,
            "signature": self.signature,
            "isAny": self.is_any,
            "kpiValues": self.task.get_kpis_for(kpi_datetime)
        }

    def mark_done(self, introspective):
        """ marks task as done (changes status) and records a task
            instrospective object: {
                as_felt_before,
                as_felt_afterwards,
                previous_activity = ""
                next_activity = ""
            }.
        """
        self.status = PlannedTaskStatus.DONE
        new_task_introspective = TaskIntrospective(
            introspective["asFeltBefore"],
            introspective["asFeltAfterwards"],
            self.id
        )
        if introspective["previousActivity"]:
            new_task_introspective.previous_activity = introspective["previousActivity"]
        if introspective["nextActivity"]:
            new_task_introspective.next_activity = introspective["nextActivity"]
        db.session.add(new_task_introspective)
        
        # try to commit
        try:
            db.session.commit()
            return True
        except:
            print("something went wrong marking planned task done or creating introspective...")
            return False


class HabitCounter(TinBase):
    """ a habit counter is a kind of planned task that takes place everyday and
        which occurrences are all recorded in one single element, that day's habit 
        counter for said habit.
    """
    __table_args__ = (
        db.UniqueConstraint("date_for_count", "habit_id", name="unique_date_for_habit_counter"),
    )
    id = db.Column(db.Integer, primary_key=True)
    date_for_count = db.Column(db.Date, nullable=False)
    count = db.Column(db.Integer, default=0, nullable=False)
    daily_target = db.Column(db.Float, nullable=False)
    signature = db.Column(db.String(100), nullable=False)
    habit_id = db.Column(db.Integer, db.ForeignKey("habit.id", ondelete="CASCADE"), nullable=False)
    # previous_activity = db.Column(db.String(120), default="")
    # as_felt_before = db.Column(db.String(120), default="")
    # next_activity = db.Column(db.String(120), default="")
    # as_felt_afterwards = db.Column(db.String(120), default="")

    def __init__(self, date_for_count, daily_target, signature, habit_id):
        self.date_for_count = date_for_count
        self.daily_target = daily_target
        self.signature = signature
        self.habit_id = habit_id

    def serialize(self):
        """ return habit counter as dict required by front end client """
        status_and_kpi = self.get_kpi()
        # print(status_and_kpi)
        # print(f"this is status: {status_and_kpi['status']}")
        return {
            "id": self.id,
            "toBeEnforced": self.habit.to_be_enforced,
            "name": self.habit.name,
            "status": status_and_kpi["status"],
            "iconName": self.habit.icon_name,
            "personalMessage": self.habit.personal_message,
            "signature": self.signature,
            "kpiValues": status_and_kpi["kpiValues"]
        }
    
    def projectize(self, date_for_kpi):
        """ return non existent habit counter as dict required by front end client """
        # grab related habit and habit_counter for kpi
        try:
            related_habit = Habit.query.filter_by(id=self.habit_id).one_or_none()
            habit_counter_for_kpi = HabitCounter.query.filter(
                HabitCounter.date_for_count == date_for_kpi.date()
            ).filter_by(habit_id=self.habit_id).one_or_none()
        except:
            print("there are two habits or habit counters with the same id, wtf!")
            return None

        if related_habit and habit_counter_for_kpi:
            # return dictionary for projected habit_counter
            status_and_kpi = habit_counter_for_kpi.get_kpi()
            status_and_kpi["kpiValues"][0]["numbers"] = [0, 0]
            return {
                "id": uuid.uuid4().hex,
                "toBeEnforced": related_habit.to_be_enforced,
                "name": related_habit.name,
                "status": status_and_kpi["status"],
                "iconName": related_habit.icon_name,
                "personalMessage": related_habit.personal_message,
                "signature": related_habit.signature,
                "kpiValues": status_and_kpi["kpiValues"]
            }
        else:
            print("we did not find such habit or habit counter, wait what?")
            return None

    def sign_latest(self):
        """ updates habit_counter to latest habit version and gets signed """
        # get latest daily_target value
        self.daily_target = self.habit.get_daily_target()
        # get latest signature
        self.signature = self.habit.signature
        # try to commit 
        try:
            db.session.commit()
        except:
            print("something went wrong commiting updated habit")    
            db.session.rollback()

    def get_kpi(self):
        """ returns a dictionary with a status key and a list of dictionaries for kpiValues key:
            - status: over, around or under, according to current value and target value
            - current_period: legend according to current target_period on habit from habit_id; 'month', 'week' or 'today'.
                'numbers' is a list of digits for current_value, which represents the sum of habitCounters count for this
                period (this month for month, this week for week, today for today)
            - lately_period: legend is 'lately'; value comes from the sum of habitCounters count for this period and some time
                before; for 'month', lately is last 28 days and last 28 days before that; for 'week', lately is last 14 days
                and last 14 days before that; for 'today', lately is last 7 days.
            - target_period: legent is 'target'; value comes from self.daily_target * 28 || 7 || 1, for 'month', 'week', 'today'
        """
        # grab habit_counters for this habit up to 56 days
        # before self.date_for_count
        past_counters = HabitCounter.query.filter(
            db.and_(
                HabitCounter.date_for_count <= self.date_for_count,
                HabitCounter.date_for_count >= self.date_for_count - timedelta(days=56)
            ) 
        ).filter_by(habit_id=self.habit_id).all()
        # prepare dictionaries and kpi_list
        dictionary_to_return = {}
        kpi_list = []
        lately_period = { "legend": "lately" }
        target_period = { "legend": "target" }

        # now check target_period for self.task, in order to 
        # correctly build kpi objects
        if self.habit.target_period == TargetPeriod.MONTHLY:
            current_period = { "legend": "month" }
            days_current = timedelta(days=29)
            days_lately = timedelta(days=56)
            times_target = 28
        elif self.habit.target_period == TargetPeriod.WEEKLY:
            current_period = { "legend": "week" }
            days_current = timedelta(days=15)
            days_lately = timedelta(days=28)
            times_target = 7 
        else:
            current_period = { "legend": "today" }
            days_current = timedelta(days=1)
            days_lately = timedelta(days=14)
            times_target = 1

        # prepare current_counters, lately_counters and target_value       
        current_counters = filter(
            lambda counter: counter.date_for_count > self.date_for_count - days_current,
            past_counters
        )
        lately_counters = filter(
            lambda counter: counter.date_for_count > self.date_for_count - days_lately,
            past_counters
        )
        target_value = int(proper_round(self.daily_target * times_target))

        # count counters!
        current_value = 0
        lately_value = 0
        # count for current
        for counter in current_counters:
            current_value += counter.count
        # count for lately
        for counter in lately_counters:
            lately_value += counter.count

        # prepare dictionary and calculate status
        if current_value <= target_value:
            # current is under target
            if current_value <= int(target_value * 0.8):
                # current is 'safely' away, under 80%
                status_value = CountStatus.UNDER.value
            else:
                # current is too close to limit
                status_value = CountStatus.AROUND.value
        else:
            # current is over target
            status_value = CountStatus.OVER.value
        dictionary_to_return["status"] = status_value


        # prepare kpi list
        current_period["numbers"] = list_value_to_digits(current_value)
        lately_period["numbers"] = list_value_to_digits(lately_value)
        target_period["numbers"] = list_value_to_digits(target_value)
        kpi_list.append(current_period)
        kpi_list.append(lately_period)
        kpi_list.append(target_period)
        dictionary_to_return["kpiValues"] = kpi_list

        return dictionary_to_return

    def record_occurrence(self, introspective):
        """ adds 1 to habit counter count! also receives an 
            introspective dictionary and creates a habit
            introspective object
        """
        self.count += 1
        new_habit_introspective = HabitIntrospective(
            introspective["asFeltBefore"],
            introspective["asFeltAfterwards"],
            self.id
        )
        if introspective["previousActivity"]:
            new_habit_introspective.previous_activity = introspective["previousActivity"]
        if introspective["nextActivity"]:
            new_habit_introspective.next_activity = introspective["nextActivity"]
        db.session.add(new_habit_introspective)

        # try to commit all changed to db
        try:
            db.session.commit()
            return True
        except:
            print("something failed updating habit counter count or creating introspective...")
            return False


class Introspective(TinBase):
    """ represents an auth user instrospective regarding a planned
        task or a habit counter occurrence, based on activities and
        feelings before and after.
    """
    __abstract__ = True
    previous_activity = db.Column(db.String(100), default="")
    next_activity = db.Column(db.String(100), default="")
    as_felt_before = db.Column(db.Enum(Feeling), nullable=False)
    as_felt_afterwards = db.Column(db.Enum(Feeling), nullable=False)

    def __init__(self, as_felt_before, as_felt_afterwards):
        self.as_felt_before = Feeling(as_felt_before)
        self.as_felt_afterwards = Feeling(as_felt_afterwards)


class TaskIntrospective(Introspective):
    """ for planned tasks """
    id = db.Column(db.Integer, primary_key=True)
    planned_task_id = db.Column(db.Integer, db.ForeignKey("planned_task.id", ondelete="CASCADE"), nullable=False)

    def __init__(self, as_felt_before, as_felt_afterwards, planned_task_id):
        self.planned_task_id = planned_task_id
        super().__init__(as_felt_before, as_felt_afterwards)


class HabitIntrospective(Introspective):
    """ for habit counters """
    id = db.Column(db.Integer, primary_key=True)
    habit_counter_id = db.Column(db.Integer, db.ForeignKey("habit_counter.id", ondelete="CASCADE"), nullable=False)

    def __init__(self, as_felt_before, as_felt_afterwards, habit_counter_id):
        self.habit_counter_id = habit_counter_id
        super().__init__(as_felt_before, as_felt_afterwards)


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