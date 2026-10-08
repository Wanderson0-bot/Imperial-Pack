from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


MIGRATION_PATH = Path(__file__).parents[1] / 'migrations' / 'versions' / '0006_integrity_controls.py'
MIGRATION_SPEC = spec_from_file_location('integrity_controls_migration', MIGRATION_PATH)
assert MIGRATION_SPEC and MIGRATION_SPEC.loader
INTEGRITY_MIGRATION = module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(INTEGRITY_MIGRATION)


def test_integrity_migration_adds_idempotency_and_refund_controls_idempotently():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE purchases (id VARCHAR(36) PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE suppliers (id VARCHAR(36) PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE customers (id VARCHAR(36) PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE users (id VARCHAR(36) PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE permissions (id VARCHAR(36) PRIMARY KEY, key VARCHAR(100) UNIQUE, description TEXT NOT NULL)'))
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            INTEGRITY_MIGRATION.upgrade()
            INTEGRITY_MIGRATION.upgrade()

        tables = set(inspect(connection).get_table_names())
        assert {'financial_categories', 'accounts_payable', 'accounts_receivable', 'cash_movements'} <= tables
        assert {'idempotency_key'} <= {column['name'] for column in inspect(connection).get_columns('purchases')}
        assert {'settlement_key'} <= {column['name'] for column in inspect(connection).get_columns('cash_movements')}
        assert {'refunded_at'} <= {column['name'] for column in inspect(connection).get_columns('accounts_payable')}
        assert {'refunded_at'} <= {column['name'] for column in inspect(connection).get_columns('accounts_receivable')}
        assert connection.scalar(text("SELECT count(*) FROM permissions WHERE key = 'purchases:cancel'")) == 1

        connection.execute(text(
            "INSERT INTO accounts_payable (id, supplier_id, description, amount, due_at, status, reference_id, created_at, updated_at) "
            "VALUES ('one', 'supplier-one', 'Compra', 1, '2026-10-05', 'PENDING', 'purchase-one', '2026-10-05', '2026-10-05')"
        ))
        with pytest.raises(IntegrityError):
            connection.execute(text(
                "INSERT INTO accounts_payable (id, supplier_id, description, amount, due_at, status, reference_id, created_at, updated_at) "
                "VALUES ('two', 'supplier-one', 'Compra duplicada', 1, '2026-10-05', 'PENDING', 'purchase-one', '2026-10-05', '2026-10-05')"
            ))

    engine.dispose()