"""empty message

Revision ID: 9a1fd825e6b1
Revises: 021285003a4b
Create Date: 2020-02-16 18:31:43.759289

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a1fd825e6b1'
down_revision = '021285003a4b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('planned_task', sa.Column('planned_date', sa.Date(), nullable=False))
    op.drop_index('unique_datetime_for_task', table_name='planned_task')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index('unique_datetime_for_task', 'planned_task', ['planned_datetime', 'task_id'], unique=True)
    op.drop_column('planned_task', 'planned_date')
    # ### end Alembic commands ###
