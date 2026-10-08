from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

MIGRATION_PATH = Path(__file__).parents[1] / 'migrations' / 'versions' / '0004_optional_customer_address.py'
MIGRATION_SPEC = spec_from_file_location('optional_customer_address_migration', MIGRATION_PATH)
assert MIGRATION_SPEC and MIGRATION_SPEC.loader
ADDRESS_MIGRATION = module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(ADDRESS_MIGRATION)


def test_optional_address_migration_merges_existing_alembic_heads():
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).parents[1] / 'migrations'))
    assert ScriptDirectory.from_config(config).get_heads() == ['0008_intelligence_training_permission']


def test_address_migration_relaxes_required_fields_and_preserves_existing_data():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE customer_addresses (id VARCHAR(36) PRIMARY KEY, customer_id VARCHAR(36) NOT NULL, label VARCHAR(80) NOT NULL, street VARCHAR(200) NOT NULL, number VARCHAR(30), complement VARCHAR(120), district VARCHAR(120), city VARCHAR(120) NOT NULL, state VARCHAR(2), postal_code VARCHAR(20), created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)'))
        connection.execute(text("INSERT INTO customer_addresses (id, customer_id, label, street, city, created_at, updated_at) VALUES ('address-1', 'customer-1', 'Principal', 'Rua preservada', 'Campinas', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            ADDRESS_MIGRATION.upgrade()
        columns = {column['name']: column for column in inspect(connection).get_columns('customer_addresses')}
        saved_address = connection.execute(text("SELECT street, city FROM customer_addresses WHERE id = 'address-1'")).one()

    assert columns['street']['nullable'] is True
    assert columns['city']['nullable'] is True
    assert saved_address == ('Rua preservada', 'Campinas')
    engine.dispose()
