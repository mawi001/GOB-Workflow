"""Add Task model

Revision ID: 8d3690928540
Revises: 9e8a5804884f
Create Date: 2019-06-18 10:55:07.252408

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8d3690928540'
down_revision = '9e8a5804884f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('tasks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('dependencies', sa.ARRAY(sa.String()), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('start', sa.DateTime(), nullable=True),
    sa.Column('end', sa.DateTime(), nullable=True),
    sa.Column('jobid', sa.Integer(), nullable=True),
    sa.Column('stepid', sa.Integer(), nullable=True),
    sa.Column('lock', sa.Integer(), nullable=True),
    sa.Column('dst_queue', sa.String(), nullable=True),
    sa.Column('key_prefix', sa.String(), nullable=True),
    sa.Column('extra_msg', sa.JSON(), nullable=True),
    sa.Column('summary', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['jobid'], ['jobs.id'], ),
    sa.ForeignKeyConstraint(['stepid'], ['jobsteps.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tasks_id'), 'tasks', ['id'], unique=False)
    op.create_index(op.f('ix_tasks_stepid'), 'tasks', ['stepid'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_tasks_stepid'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_id'), table_name='tasks')
    op.drop_table('tasks')
    # ### end Alembic commands ###