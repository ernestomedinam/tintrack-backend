from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import enum
import string
import os
from base64 import b64encode
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta

db = SQLAlchemy()

class TargetPeriod(enum.Enum):
    DAILY = "Daily"
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"

class PlannedTaskStatus(enum.Enum):
    PENDING = "Pending"
    MISSED = "Missed"
    DONE = "Done"

class User(db.Model):
    """ a tintrack user. each user has a personal salt to be mixed with
        password before hashing and storing."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="J Doe")
    email = db.Column(db.String(120), unique=True, nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    password_hash = db.Column(db.String(250), nullable=False, default="default")
    user_salt = db.Column(db.String(120), nullable=False)
    tasks = db.relationship("Task", backref="user", lazy=True)
    habits = db.relationship("Habit", backref="user", lazy=True)

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


class Activity(db.Model):
    """ an activity that has a name and a reason to be included
        in someone's routine, as a habit or a task."""
    __abstract__ = True
    name = db.Column(db.String(120), nullable=False)
    personal_message = db.Column(db.String(250), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_edited_at = db.Column(db.DateTime, nullable=False)

class Task(Activity):
    """ a task is a periodic activity that takes place in specific times
        and dates."""
    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="unique_task_for_user"),
    )
    id = db.Column(db.Integer, primary_key=True)
    duration_estimate = db.Column(db.Integer, default=0, nullable=False)
    icon_name = db.Column(db.String(50), nullable=False, default="default-task")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    planned_tasks = db.relationship("PlannedTask", backref="task", lazy=True)
    week_schedules = db.relationship("WeekSchedule", backref="task", lazy=True)

    def __init__(self, name, personal_message, duration_estimate, icon_name, user_id):
        self.name = name.strip()
        self.personal_message = personal_message.strip()
        self.last_edited_at = datetime.now()
        self.duration_estimate = duration_estimate
        self.icon_name = icon_name
        self.user_id = user_id

class Habit(Activity):
    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="unique_habit_for_user"),
    )
    id = db.Column(db.Integer, primary_key=True)
    to_be_enforced = db.Column(db.Boolean, nullable=False)
    target_period = db.Column(db.Enum(TargetPeriod), nullable=False)
    target_value = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    habit_counters = db.relationship("HabitCounter", backref="habit", lazy=True)

    def __init__(self, name, personal_message, to_be_enforced, last_edited_at, target_period, target_value, user_id):
        self.name = name.strip()
        self.personal_message = personal_message.strip()
        self.to_be_enforced = to_be_enforced
        self.last_edited_at = datetime.now()
        self.target_period = target_period
        self.target_value = target_value
        self.user_id = user_id

class PlannedTask(db.Model):
    __table_args__ = (
        db.UniqueConstraint("planned_datetime", "task_id", name="unique_datetime_for_task"),
    )
    id = db.Column(db.Integer, primary_key=True)
    planned_datetime = db.Column(db.DateTime, nullable=False)
    # duration is registered in seconds
    duration_estimate = db.Column(db.Integer, nullable=False)
    registered_duration = db.Column(db.Integer)
    status = db.Column(db.Enum(PlannedTaskStatus), nullable=False, server_default="PENDING")
    marked_done_at = db.Column(db.DateTime)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    previous_activity = db.Column(db.String(120), default="")
    as_felt_before = db.Column(db.String(120), default="")
    next_activity = db.Column(db.String(120), default="")
    as_felt_afterwards = db.Column(db.String(120), default="")

    def __init__(self, planned_datetime, duration_estimate, task_id):
        self.planned_datetime = planned_datetime
        self.duration_estimate = duration_estimate
        self.task_id = task_id

class HabitCounter(db.Model):
    __table_args__ = (
        db.UniqueConstraint("date_for_count", "habit_id", name="unique_date_for_habit_counter"),
    )
    id = db.Column(db.Integer, primary_key=True)
    date_for_count = db.Column(db.Date, nullable=False)
    count = db.Column(db.Integer, default=0, nullable=False)
    daily_target = db.Column(db.Integer, nullable=False)
    habit_id = db.Column(db.Integer, db.ForeignKey("habit.id"), nullable=False)
    previous_activity = db.Column(db.String(120), default="")
    as_felt_before = db.Column(db.String(120), default="")
    next_activity = db.Column(db.String(120), default="")
    as_felt_afterwards = db.Column(db.String(120), default="")

    def __init__(self, date_for_count, daily_target, habit_id):
        self.date_for_count = date_for_count
        self.daily_target = daily_target
        self.habit_id = habit_id

class WeekSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_number = db.Column(db.Integer, nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    weekdays = db.relationship("Weekday", backref="week_schedule", lazy=True)

    def __init__(self, week_number):
        self.week_number = week_number

class Weekday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day_number = db.Column(db.Integer, nullable=False)
    week_schedule_id = db.Column(db.Integer, db.ForeignKey("week_schedule.id"), nullable=True)
    daytimes = db.relationship("Daytime", backref="weekday", lazy=True)

    def __init__(self, day_number, week_schedule_id):
        self.day_number = day_number
        self.week_schedule_id = week_schedule_id


class Daytime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time_of_day = db.Column(db.String(10), nullable=False)
    weekday_id = db.Column(db.Integer, db.ForeignKey("weekday.id"), nullable=True)

    def __init__(self, time_of_day, weekday_id):
        self.time_of_day = time_of_day
        self.weekday_id = weekday_id
