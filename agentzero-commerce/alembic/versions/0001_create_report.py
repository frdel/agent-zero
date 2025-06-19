"""create report table"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'report',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('property_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('params', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
    )

def downgrade():
    op.drop_table('report')
