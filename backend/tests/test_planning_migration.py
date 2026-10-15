import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect, make_url, select, text
from sqlalchemy.dialects import postgresql

from app.database.base import Base
from app.database.models import Permission, Product, Role, RolePermission


MIGRATION_PATH = Path(__file__).parents[1] / 'migrations' / 'versions' / '0010_planning_workspace.py'
SPEC = spec_from_file_location('planning_workspace_migration', MIGRATION_PATH)
assert SPEC and SPEC.loader
MIGRATION = module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def _is_local_postgres_test_url(url: str) -> bool:
    parsed_url = make_url(url)
    return (
        parsed_url.get_backend_name() == 'postgresql'
        and parsed_url.host in {'localhost', '127.0.0.1', '::1'}
        and (parsed_url.database or '').lower().endswith('_test')
    )


def test_permission_grant_compiles_with_explicit_postgresql_parameter_type():
    statement = MIGRATION._permission_grant_statement(
        Role.__table__.c.id.type,
        Role.__table__.c.name.type,
        RolePermission.__table__.c.role_id.type,
        RolePermission.__table__.c.permission_id.type,
    )
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert compiled.count('CAST(%(permission_id)s AS VARCHAR(36))') == 2
    assert "roles.name = %(name_1)s" in compiled


@pytest.mark.parametrize('host', ['localhost', '127.0.0.1', '[::1]'])
def test_postgresql_test_url_accepts_only_supported_loopback_hosts(host):
    assert _is_local_postgres_test_url(f'postgresql+psycopg://user@{host}:5432/app_test')


@pytest.mark.parametrize('host', ['db.neon.tech', 'localhost.example.com', '127.0.0.1.nip.io'])
def test_postgresql_test_url_rejects_remote_hosts_and_aliases(host):
    assert not _is_local_postgres_test_url(f'postgresql+psycopg://user@{host}:5432/app_test')


def test_postgresql_test_url_requires_test_database_name():
    assert not _is_local_postgres_test_url('postgresql+psycopg://user@localhost:5432/app')


def test_planning_migration_creates_relational_tables_and_admin_permission():
    """SQLite covers migration structure/idempotency, not PostgreSQL compatibility."""
    engine = create_engine('sqlite://')
    planning_tables = {'plannings', 'planning_tasks', 'planning_goals', 'planning_entity_links', 'planning_opportunity_dismissals'}
    with engine.begin() as connection:
        legacy_tables = [table for table in Base.metadata.sorted_tables if table.name not in planning_tables]
        Base.metadata.create_all(connection, tables=legacy_tables)
        connection.execute(Role.__table__.insert().values(id='admin-role', name='general_admin', is_system=True))
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            MIGRATION.upgrade()
            MIGRATION.upgrade()

        assert planning_tables <= set(inspect(connection).get_table_names())
        inspector = inspect(connection)
        expected_columns = {
            'plannings': set(Base.metadata.tables['plannings'].columns.keys()),
            'planning_tasks': set(Base.metadata.tables['planning_tasks'].columns.keys()),
            'planning_goals': set(Base.metadata.tables['planning_goals'].columns.keys()),
            'planning_entity_links': set(Base.metadata.tables['planning_entity_links'].columns.keys()),
            'planning_opportunity_dismissals': set(Base.metadata.tables['planning_opportunity_dismissals'].columns.keys()),
        }
        for table_name, columns in expected_columns.items():
            assert columns <= {column['name'] for column in inspector.get_columns(table_name)}
        goal_fk = next(foreign_key for foreign_key in inspector.get_foreign_keys('planning_goals') if foreign_key['constrained_columns'] == ['planning_id'])
        assert goal_fk['referred_table'] == 'plannings'
        assert goal_fk['options']['ondelete'] == 'SET NULL'
        margin_column = next(column for column in inspector.get_columns('products') if column['name'] == 'target_margin_percent')
        assert margin_column['nullable'] is False
        assert margin_column['type'].precision == Product.__table__.c.target_margin_percent.type.precision == 8
        assert margin_column['type'].scale == Product.__table__.c.target_margin_percent.type.scale == 4
        permission = connection.execute(select(Permission.__table__.c.id, Permission.__table__.c.description).where(Permission.__table__.c.key == 'planning:manage')).one()
        assert permission.description == 'Create and manage company planning'
        assert connection.scalar(select(Role.__table__.c.name).where(Role.__table__.c.id == 'admin-role')) == 'general_admin'
        assert connection.scalar(text('SELECT count(*) FROM role_permissions WHERE role_id = :role_id AND permission_id = :permission_id'), {'role_id': 'admin-role', 'permission_id': permission.id}) == 1

    engine.dispose()


def test_planning_migration_grants_permission_idempotently_on_postgresql():
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL is not configured; PostgreSQL migration integration was not run.')

    if not _is_local_postgres_test_url(url):
        pytest.fail('TEST_POSTGRES_URL must target a local PostgreSQL database whose name ends in _test.')

    admin_engine = create_engine(url, connect_args={'connect_timeout': 3})
    schema = f'ip_planning_{uuid4().hex[:16]}'
    schema_created = False
    engine = None
    try:
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        schema_created = True
        engine = create_engine(url, connect_args={'connect_timeout': 3, 'options': f'-csearch_path={schema}'})
        parent_metadata = MetaData()
        parent_tables = [
            Table(name, parent_metadata, Column('id', String(36), primary_key=True))
            for name in ('users', 'customers', 'suppliers', 'products', 'purchases', 'orders', 'accounts_payable', 'accounts_receivable')
        ]
        rbac_tables = [Role.__table__, Permission.__table__, RolePermission.__table__]
        with engine.begin() as connection:
            Base.metadata.create_all(connection, tables=rbac_tables)
            parent_metadata.create_all(connection, tables=parent_tables)
            connection.execute(Role.__table__.insert().values(id='admin-role', name='general_admin', is_system=True))

            column_types = connection.execute(text("""
                SELECT table_name, column_name, format_type(attribute.atttypid, attribute.atttypmod) AS sql_type
                FROM information_schema.columns AS column_info
                JOIN pg_attribute AS attribute ON attribute.attname = column_info.column_name
                JOIN pg_class AS relation ON relation.oid = attribute.attrelid AND relation.relname = column_info.table_name
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace AND namespace.nspname = :schema
                WHERE column_info.table_schema = :schema
                  AND (column_info.table_name, column_info.column_name) IN (
                    ('roles', 'id'), ('permissions', 'id'),
                    ('role_permissions', 'role_id'), ('role_permissions', 'permission_id')
                  )
            """), {'schema': schema})
            assert {(row.table_name, row.column_name, row.sql_type) for row in column_types} == {
                ('roles', 'id', 'character varying(36)'),
                ('permissions', 'id', 'character varying(36)'),
                ('role_permissions', 'role_id', 'character varying(36)'),
                ('role_permissions', 'permission_id', 'character varying(36)'),
            }

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                MIGRATION.upgrade()
                MIGRATION.upgrade()

            permission_id = connection.scalar(text("SELECT id FROM permissions WHERE key = 'planning:manage'"))
            assert permission_id is not None
            assert connection.scalar(text("SELECT count(*) FROM role_permissions WHERE role_id = 'admin-role' AND permission_id = :permission_id"), {'permission_id': permission_id}) == 1
    finally:
        try:
            if engine is not None:
                engine.dispose()
        finally:
            try:
                if schema_created:
                    with admin_engine.begin() as connection:
                        connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
            finally:
                admin_engine.dispose()
