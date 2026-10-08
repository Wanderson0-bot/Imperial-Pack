from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

MIGRATION_PATH = Path(__file__).parents[1] / 'migrations' / 'versions' / '0003_commercial_links.py'
MIGRATION_SPEC = spec_from_file_location('commercial_links_migration', MIGRATION_PATH)
assert MIGRATION_SPEC and MIGRATION_SPEC.loader
COMMERCIAL_MIGRATION = module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(COMMERCIAL_MIGRATION)

OPERATIONAL_MIGRATION_PATH = Path(__file__).parents[1] / 'migrations' / 'versions' / '0005_operational_signals.py'
OPERATIONAL_MIGRATION_SPEC = spec_from_file_location('operational_signals_migration', OPERATIONAL_MIGRATION_PATH)
assert OPERATIONAL_MIGRATION_SPEC and OPERATIONAL_MIGRATION_SPEC.loader
OPERATIONAL_MIGRATION = module_from_spec(OPERATIONAL_MIGRATION_SPEC)
OPERATIONAL_MIGRATION_SPEC.loader.exec_module(OPERATIONAL_MIGRATION)


def test_commercial_migration_adds_columns_and_indexes_to_legacy_tables():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE suppliers (id VARCHAR(36) PRIMARY KEY, name VARCHAR(180) NOT NULL)'))
        connection.execute(text('CREATE TABLE customers (id VARCHAR(36) PRIMARY KEY, origin VARCHAR(30) NOT NULL)'))
        connection.execute(text('CREATE TABLE orders (id VARCHAR(36) PRIMARY KEY, source VARCHAR(30) NOT NULL)'))
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            COMMERCIAL_MIGRATION.upgrade()
        assert 'location' in {column['name'] for column in inspect(connection).get_columns('suppliers')}
        assert 'external_id' in {column['name'] for column in inspect(connection).get_columns('customers')}
        assert 'external_id' in {column['name'] for column in inspect(connection).get_columns('orders')}
        index_names = set(connection.scalars(text("SELECT name FROM sqlite_master WHERE type = 'index'")))
        assert 'uq_suppliers_normalized_name' in index_names
        assert 'uq_customers_origin_external_id' in index_names
        assert 'uq_orders_source_external_id' in index_names
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            COMMERCIAL_MIGRATION.upgrade()
    engine.dispose()


def test_commercial_migration_refuses_ambiguous_duplicate_supplier_names():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE suppliers (id VARCHAR(36) PRIMARY KEY, name VARCHAR(180) NOT NULL)'))
        connection.execute(text('CREATE TABLE customers (id VARCHAR(36) PRIMARY KEY, origin VARCHAR(30) NOT NULL)'))
        connection.execute(text('CREATE TABLE orders (id VARCHAR(36) PRIMARY KEY, source VARCHAR(30) NOT NULL)'))
        connection.execute(text("INSERT INTO suppliers (id, name) VALUES ('1', 'Supplier A'), ('2', ' supplier a ')"))
        context = MigrationContext.configure(connection)
        try:
            with Operations.context(context):
                COMMERCIAL_MIGRATION.upgrade()
        except RuntimeError as error:
            assert 'duplicate supplier names' in str(error)
        else:
            raise AssertionError('Migration should stop when normalized supplier names are duplicated.')
    engine.dispose()


def test_operational_migration_preserves_legacy_rows_and_is_repeatable():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE partners (id VARCHAR(36) PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE products (id VARCHAR(36) PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE customers (id VARCHAR(36) PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE partner_alerts (id VARCHAR(36) PRIMARY KEY, partner_id VARCHAR(36) NOT NULL REFERENCES partners(id), product_id VARCHAR(36) REFERENCES products(id), alert_type VARCHAR(50) NOT NULL, message TEXT NOT NULL, created_at DATETIME NOT NULL, resolved_at DATETIME)'))
        connection.execute(text('CREATE TABLE partner_opportunities (id VARCHAR(36) PRIMARY KEY, partner_id VARCHAR(36) NOT NULL REFERENCES partners(id), product_id VARCHAR(36) NOT NULL REFERENCES products(id), evidence JSON NOT NULL, status VARCHAR(20) NOT NULL, created_at DATETIME NOT NULL)'))
        connection.execute(text("INSERT INTO partners (id) VALUES ('partner-1')"))
        connection.execute(text("INSERT INTO products (id) VALUES ('product-1')"))
        connection.execute(text("INSERT INTO customers (id) VALUES ('customer-1')"))
        connection.execute(text("INSERT INTO partner_alerts (id, partner_id, product_id, alert_type, message, created_at) VALUES ('alert-1', 'partner-1', 'product-1', 'legacy', 'Mensagem preservada', '2026-01-01')"))
        connection.execute(text("INSERT INTO partner_opportunities (id, partner_id, product_id, evidence, status, created_at) VALUES ('opportunity-1', 'partner-1', 'product-1', '{}', 'OPEN', '2026-01-01')"))

        context = MigrationContext.configure(connection)
        with Operations.context(context):
            OPERATIONAL_MIGRATION.upgrade()

        alert = connection.execute(text("SELECT entity_type, status, message FROM partner_alerts WHERE id = 'alert-1'")).one()
        opportunity = connection.execute(text("SELECT entity_type, status FROM partner_opportunities WHERE id = 'opportunity-1'")).one()
        assert alert == ('partner', 'OPEN', 'Mensagem preservada')
        assert opportunity == ('partner', 'OPEN')
        alert_columns = {column['name']: column for column in inspect(connection).get_columns('partner_alerts')}
        opportunity_columns = {column['name']: column for column in inspect(connection).get_columns('partner_opportunities')}
        assert alert_columns['partner_id']['nullable']
        assert opportunity_columns['partner_id']['nullable']
        assert opportunity_columns['product_id']['nullable']
        index_names = set(connection.scalars(text("SELECT name FROM sqlite_master WHERE type = 'index'")))
        assert 'uq_partner_alerts_dedupe_key' in index_names
        assert 'uq_partner_opportunities_dedupe_key' in index_names

        context = MigrationContext.configure(connection)
        with Operations.context(context):
            OPERATIONAL_MIGRATION.upgrade()
    engine.dispose()