"""Add purchase document, observations and item discounts/descriptions.

Revision ID: 0002_purchase_details
Revises: 0001_initial
"""
import sqlalchemy as sa
from alembic import op

revision = '0002_purchase_details'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    columns = {column_info['name'] for column_info in sa.inspect(op.get_bind()).get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def upgrade():
    _add_column_if_missing('purchases', sa.Column('document_number', sa.String(length=100), nullable=True))
    _add_column_if_missing('purchases', sa.Column('observations', sa.Text(), nullable=True))
    _add_column_if_missing('purchases', sa.Column('discount_total', sa.Numeric(14, 2), server_default=sa.text('0'), nullable=False))
    _add_column_if_missing('purchase_items', sa.Column('discount', sa.Numeric(14, 2), server_default=sa.text('0'), nullable=False))
    _add_column_if_missing('purchase_items', sa.Column('description', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('purchase_items', 'description')
    op.drop_column('purchase_items', 'discount')
    op.drop_column('purchases', 'discount_total')
    op.drop_column('purchases', 'observations')
    op.drop_column('purchases', 'document_number')