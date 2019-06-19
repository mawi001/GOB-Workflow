"""add process_id to Task model

Revision ID: 0dec5fd9bb53
Revises: 8d3690928540
Create Date: 2019-06-19 11:19:21.712843

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0dec5fd9bb53'
down_revision = '8d3690928540'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('tasks', sa.Column('process_id', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('tasks', 'process_id')
    # ### end Alembic commands ###