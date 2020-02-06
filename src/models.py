from flask_sqlalchemy import SQLAlchemy
import enum

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
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    password_hash = db.Column(db.String(250), nullable=False)
    user_salt = db.Column(db.String(120), nullable=False)
    tasks = db.relationship("Task", backref="user", lazy=True)
    habits = db.relationship("Habit", backref="user", lazy=True)

class Activity(db.Model):
    __abstract__ = True
    name = db.Column(db.String(120), nullable=False)
    personal_message = db.Column(db.String(250), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_edited_at = db.Column(db.DateTime, nullable=False)

class Task(Activity):
    id = db.Column(db.Integer, primary_key=True)
    duration_estimate = db.Column(db.Integer, default=0, nullable=False)
    icon_name = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    planned_tasks = db.relationship("PlannedTask", backref="task", lazy=True)
    week_schedules = db.relationship("WeekSchedule", backref="task", lazy=True)

class Habit(Activity):
    id = db.Column(db.Integer, primary_key=True)
    target_period = db.Column(db.Enum(TargetPeriod), nullable=False)
    target_value = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    habit_counters = db.relationship("HabitCounter", backref="habit", lazy=True)

class PlannedTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    planned_datetime = db.Column(db.DateTime, nullable=False)
    # duration is registered in seconds
    duration_estimate = db.Column(db.Integer, nullable=False)
    registered_duration = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum(PlannedTaskStatus), nullable=False)
    marked_done_at = db.Column(db.DateTime, nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    previous_activity = db.Column(db.String(120), default="")
    as_felt_before = db.Column(db.String(120), default="")
    next_activity = db.Column(db.String(120), default="")
    as_felt_afterwards = db.Column(db.String(120), default="")

class HabitCounter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_for_count = db.Column(db.Date, nullable=False)
    to_be_enforced = db.Column(db.Boolean, nullable=False, default=True)
    count = db.Column(db.Integer, default=0, nullable=False)
    daily_target = db.Column(db.Integer, nullable=False)
    habit_id = db.Column(db.Integer, db.ForeignKey("habit.id"), nullable=False)
    previous_activity = db.Column(db.String(120), default="")
    as_felt_before = db.Column(db.String(120), default="")
    next_activity = db.Column(db.String(120), default="")
    as_felt_afterwards = db.Column(db.String(120), default="")

class WeekSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_number = db.Column(db.Integer, nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    weekdays = db.relationship("Weekday", backref="week_schedule", lazy=True)

class Weekday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day_number = db.Column(db.Integer, nullable=False)
    week_schedule_id = db.Column(db.Integer, db.ForeignKey("week_schedule.id"), nullable=True)
    daytimes = db.relationship("Daytime", backref="weekday", lazy=True)

class Daytime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time_of_day = db.Column(db.String(10), nullable=False)
    weekday_id = db.Column(db.Integer, db.ForeignKey("weekday.id"), nullable=True)

