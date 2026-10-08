"""Add supplier location and optional external commerce identifiers.

Revision ID: 0003_commercial_links
Revises: 0002_purchase_details
"""
import sqlalchemy as sa
from alembic import op

revision = '0003_commercial_links'
down_revision = '0002_purchase_details'
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    columns = {column_info['name'] for column_info in sa.inspect(op.get_bind()).get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def _create_index_if_missing(name: str, table_name: str, columns: list[object], unique: bool = False) -> None:
    connection = op.get_bind()
    if connection.dialect.name == 'sqlite':
        exists = connection.scalar(sa.text("SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = :name"), {'name': name})
    else:
        indexes = {index['name'] for index in sa.inspect(connection).get_indexes(table_name)}
        exists = name in indexes
    if not exists:
        op.create_index(name, table_name, columns, unique=unique)


def upgrade():
    _add_column_if_missing('suppliers', sa.Column('location', sa.String(length=240), nullable=True))
    _add_column_if_missing('customers', sa.Column('external_id', sa.String(length=120), nullable=True))
    _add_column_if_missing('orders', sa.Column('external_id', sa.String(length=120), nullable=True))

    duplicate_name = op.get_bind().execute(sa.text('SELECT lower(trim(name)), count(*) FROM suppliers GROUP BY lower(trim(name)) HAVING count(*) > 1 LIMIT 1')).first()
    if duplicate_name:
        raise RuntimeError('Normalize duplicate supplier names before applying the commercial links migration.')

    _create_index_if_missing('uq_suppliers_normalized_name', 'suppliers', [sa.text('lower(trim(name))')], unique=True)
    _create_index_if_missing('uq_customers_origin_external_id', 'customers', ['origin', 'external_id'], unique=True)
    _create_index_if_missing('uq_orders_source_external_id', 'orders', ['source', 'external_id'], unique=True)


def downgrade():
    pass