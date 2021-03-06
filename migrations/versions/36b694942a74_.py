"""empty message

Revision ID: 36b694942a74
Revises: 
Create Date: 2020-02-22 14:46:19.337520

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '36b694942a74'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('token_blacklist',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('jti', sa.String(length=36), nullable=False),
    sa.Column('token_type', sa.String(length=10), nullable=False),
    sa.Column('user_identity', sa.String(length=50), nullable=False),
    sa.Column('revoked', sa.Boolean(), nullable=False),
    sa.Column('expires', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('date_of_birth', sa.Date(), nullable=False),
    sa.Column('password_hash', sa.String(length=250), nullable=False),
    sa.Column('user_salt', sa.String(length=120), nullable=False),
    sa.Column('ranking', sa.Enum('STARTER', 'ENROLLED', 'EXPERIENCED', 'VETERAN', name='userranking'), nullable=False),
    sa.Column('member_since', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    mysql_engine='InnoDB'
    )
    op.create_table('habit',
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('personal_message', sa.String(length=250), nullable=False),
    sa.Column('signature', sa.String(length=100), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_edited_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('to_be_enforced', sa.Boolean(), nullable=False),
    sa.Column('target_period', sa.Enum('DAILY', 'WEEKLY', 'MONTHLY', name='targetperiod'), nullable=False),
    sa.Column('target_value', sa.Integer(), nullable=False),
    sa.Column('icon_name', sa.String(length=50), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'name', name='unique_habit_for_user')
    )
    op.create_table('task',
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('personal_message', sa.String(length=250), nullable=False),
    sa.Column('signature', sa.String(length=100), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_edited_at', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('duration_estimate', sa.Integer(), nullable=False),
    sa.Column('icon_name', sa.String(length=50), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'name', name='unique_task_for_user')
    )
    op.create_table('habit_counter',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('date_for_count', sa.Date(), nullable=False),
    sa.Column('count', sa.Integer(), nullable=False),
    sa.Column('daily_target', sa.Float(), nullable=False),
    sa.Column('signature', sa.String(length=100), nullable=False),
    sa.Column('habit_id', sa.Integer(), nullable=False),
    sa.Column('previous_activity', sa.String(length=120), nullable=True),
    sa.Column('as_felt_before', sa.String(length=120), nullable=True),
    sa.Column('next_activity', sa.String(length=120), nullable=True),
    sa.Column('as_felt_afterwards', sa.String(length=120), nullable=True),
    sa.ForeignKeyConstraint(['habit_id'], ['habit.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('date_for_count', 'habit_id', name='unique_date_for_habit_counter')
    )
    op.create_table('planned_task',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('planned_datetime', sa.DateTime(), nullable=False),
    sa.Column('planned_date', sa.Date(), nullable=False),
    sa.Column('is_any', sa.Boolean(), nullable=False),
    sa.Column('duration_estimate', sa.Integer(), nullable=False),
    sa.Column('registered_duration', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'DONE', name='plannedtaskstatus'), nullable=False),
    sa.Column('marked_done_at', sa.DateTime(), nullable=True),
    sa.Column('signature', sa.String(length=100), nullable=False),
    sa.Column('task_id', sa.Integer(), nullable=False),
    sa.Column('previous_activity', sa.String(length=120), nullable=True),
    sa.Column('as_felt_before', sa.String(length=120), nullable=True),
    sa.Column('next_activity', sa.String(length=120), nullable=True),
    sa.Column('as_felt_afterwards', sa.String(length=120), nullable=True),
    sa.ForeignKeyConstraint(['task_id'], ['task.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    mysql_engine='InnoDB'
    )
    op.create_table('task_kpi',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('longest_streak', sa.Integer(), nullable=False),
    sa.Column('best_average', sa.Float(), nullable=False),
    sa.Column('task_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['task.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    mysql_engine='InnoDB'
    )
    op.create_table('week_schedule',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('week_number', sa.Integer(), nullable=False),
    sa.Column('task_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['task.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    mysql_engine='InnoDB'
    )
    op.create_table('weekday',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('day_number', sa.Integer(), nullable=False),
    sa.Column('week_schedule_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['week_schedule_id'], ['week_schedule.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    mysql_engine='InnoDB'
    )
    op.create_table('daytime',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('time_of_day', sa.String(length=10), nullable=False),
    sa.Column('weekday_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['weekday_id'], ['weekday.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    mysql_engine='InnoDB'
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('daytime')
    op.drop_table('weekday')
    op.drop_table('week_schedule')
    op.drop_table('task_kpi')
    op.drop_table('planned_task')
    op.drop_table('habit_counter')
    op.drop_table('task')
    op.drop_table('habit')
    op.drop_table('user')
    op.drop_table('token_blacklist')
    # ### end Alembic commands ###
