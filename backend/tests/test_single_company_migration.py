from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


MIGRATION_PATH = Path(__file__).parents[1] / 'migrations' / 'versions' / '0007_single_company_indexes.py'
MIGRATION_SPEC = spec_from_file_location('single_company_indexes_migration', MIGRATION_PATH)
assert MIGRATION_SPEC and MIGRATION_SPEC.loader
MIGRATION = module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)


def test_single_company_index_migration_is_idempotent_and_reversible():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text(
            'CREATE TABLE partner_opportunities (id VARCHAR(36) PRIMARY KEY, customer_id VARCHAR(36))'
        ))
        with Operations.context(MigrationContext.configure(connection)):
            MIGRATION.upgrade()
            MIGRATION.upgrade()

        indexes = {item['name'] for item in inspect(connection).get_indexes('partner_opportunities')}
        assert 'ix_partner_opportunities_customer_id' in indexes

        with Operations.context(MigrationContext.configure(connection)):
            MIGRATION.downgrade()

        indexes = {item['name'] for item in inspect(connection).get_indexes('partner_opportunities')}
        assert 'ix_partner_opportunities_customer_id' not in indexes
    engine.dispose()
