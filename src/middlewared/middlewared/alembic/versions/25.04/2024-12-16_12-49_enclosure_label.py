"""Rename `enclosure_label` table

Revision ID: 19cdc9f2d2df
Revises: aea6bced4328
Create Date: 2024-12-16 12:49:19.950812+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '19cdc9f2d2df'
down_revision = 'aea6bced4328'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute("ALTER TABLE truenas_enclosurelabel RENAME TO enclosure_label")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
