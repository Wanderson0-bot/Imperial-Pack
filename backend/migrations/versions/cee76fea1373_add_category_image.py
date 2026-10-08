"""add category image

Revision ID: cee76fea1373
Revises: 0002_purchase_details
Create Date: 2026-10-01 17:18:24.001214
"""

from alembic import op
import sqlalchemy as sa


revision = 'cee76fea1373'
down_revision = '0002_purchase_details'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'product_categories',
        sa.Column('image_url', sa.Text(), nullable=True)
    )


def downgrade():
    op.drop_column('product_categories', 'image_url')