"""user in jobs table

Revision ID: 9c0cb17f8956
Revises: 22e154a69341
Create Date: 2020-01-29 13:04:32.554273

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c0cb17f8956'
down_revision = '22e154a69341'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('jobs', sa.Column('user', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('jobs', 'user')
    # ### end Alembic commands ###
