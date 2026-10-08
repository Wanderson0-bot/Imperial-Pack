"""Add idempotency, settlement, and purchase cancellation controls.

Revision ID: 0006_integrity_controls
Revises: 0005_operational_signals
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.database.base import Base
from app.database import models as _models

revision = '0006_integrity_controls'
down_revision = '0005_operational_signals'
branch_labels = None
depends_on = None


FINANCIAL_TABLES = (
    'financial_categories',
    'accounts_payable',
    'accounts_receivable',
    'cash_movements',
)


def _create_missing_financial_tables() -> None:
    connection = op.get_bind()
    for table_name in FINANCIAL_TABLES:
        if not sa.inspect(connection).has_table(table_name):
            Base.metadata.tables[table_name].create(connection, checkfirst=False)


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    columns = {item['name'] for item in sa.inspect(op.get_bind()).get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def _create_unique_index(name: str, table_name: str, expression: str, predicate: str | None = None) -> None:
    connection = op.get_bind()
    indexes = {item['name'] for item in sa.inspect(connection).get_indexes(table_name)}
    if name not in indexes:
        where = f' WHERE {predicate}' if predicate else ''
        connection.execute(sa.text(f'CREATE UNIQUE INDEX {name} ON {table_name} ({expression}){where}'))


def _ensure_no_duplicate_references(table_name: str) -> None:
    duplicate = op.get_bind().execute(sa.text(
        f'SELECT reference_id FROM {table_name} WHERE reference_id IS NOT NULL GROUP BY reference_id HAVING count(*) > 1 LIMIT 1'
    )).first()
    if duplicate:
        raise RuntimeError(f'Remove duplicate non-null references from {table_name} before applying integrity controls.')


def upgrade():
    _create_missing_financial_tables()
    _add_column_if_missing('purchases', sa.Column('idempotency_key', sa.String(120), nullable=True))
    _add_column_if_missing('cash_movements', sa.Column('settlement_key', sa.String(180), nullable=True))
    _add_column_if_missing('accounts_payable', sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing('accounts_receivable', sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True))

    _ensure_no_duplicate_references('accounts_payable')
    _ensure_no_duplicate_references('accounts_receivable')
    _create_unique_index('uq_purchases_idempotency_key', 'purchases', 'idempotency_key')
    _create_unique_index('uq_cash_movements_settlement_key', 'cash_movements', 'settlement_key')
    _create_unique_index('uq_accounts_payable_reference_id', 'accounts_payable', 'reference_id', 'reference_id IS NOT NULL')
    _create_unique_index('uq_accounts_receivable_reference_id', 'accounts_receivable', 'reference_id', 'reference_id IS NOT NULL')

    permission_exists = op.get_bind().scalar(sa.text("SELECT 1 FROM permissions WHERE key = 'purchases:cancel'"))
    if not permission_exists:
        op.get_bind().execute(sa.text(
            'INSERT INTO permissions (id, key, description) VALUES (:id, :key, :description)'
        ), {'id': str(uuid4()), 'key': 'purchases:cancel', 'description': 'Cancel and reverse purchases'})


def downgrade():
    op.drop_index('uq_accounts_receivable_reference_id', table_name='accounts_receivable')
    op.drop_index('uq_accounts_payable_reference_id', table_name='accounts_payable')
    op.drop_index('uq_cash_movements_settlement_key', table_name='cash_movements')
    op.drop_index('uq_purchases_idempotency_key', table_name='purchases')
    op.drop_column('accounts_receivable', 'refunded_at')
    op.drop_column('accounts_payable', 'refunded_at')
    op.drop_column('cash_movements', 'settlement_key')
    op.drop_column('purchases', 'idempotency_key')
    op.get_bind().execute(sa.text("DELETE FROM permissions WHERE key = 'purchases:cancel'"))