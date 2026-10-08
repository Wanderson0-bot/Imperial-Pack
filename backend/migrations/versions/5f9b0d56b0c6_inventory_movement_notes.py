"""add notes to inventory movements

Revision ID: 5f9b0d56b0c6
Revises: 0004_optional_customer_address
Create Date: 2026-10-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '5f9b0d56b0c6'
down_revision = '0004_optional_customer_address'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('inventory_movements', sa.Column('notes', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('inventory_movements', 'notes')
