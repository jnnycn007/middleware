"""Add login_banner column

Revision ID: 1307a8e6a8b6
Revises: d8bfbf4e277e
Create Date: 2024-06-24 12:57:36.048308+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1307a8e6a8b6'
down_revision = 'd8bfbf4e277e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adv_login_banner', sa.Text(), nullable=False, server_default=''))



def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.drop_column('adv_login_banner')
