from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select, text

from app.database.base import Base
from app.database.models import Permission, Role


MIGRATION_PATH = Path(__file__).parents[1] / 'migrations' / 'versions' / '0010_planning_workspace.py'
SPEC = spec_from_file_location('planning_workspace_migration', MIGRATION_PATH)
assert SPEC and SPEC.loader
MIGRATION = module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def test_planning_migration_creates_relational_tables_and_admin_permission():
    engine = create_engine('sqlite://')
    planning_tables = {'plannings', 'planning_tasks', 'planning_goals', 'planning_entity_links', 'planning_opportunity_dismissals'}
    with engine.begin() as connection:
        legacy_tables = [table for table in Base.metadata.sorted_tables if table.name not in planning_tables]
        Base.metadata.create_all(connection, tables=legacy_tables)
        connection.execute(Role.__table__.insert().values(id='admin-role', name='general_admin', is_system=True))
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            MIGRATION.upgrade()

        assert planning_tables <= set(inspect(connection).get_table_names())
        permission = connection.execute(select(Permission.__table__.c.id, Permission.__table__.c.description).where(Permission.__table__.c.key == 'planning:manage')).one()
        assert permission.description == 'Create and manage company planning'
        assert connection.scalar(select(Role.__table__.c.name).where(Role.__table__.c.id == 'admin-role')) == 'general_admin'
        assert connection.scalar(text('SELECT count(*) FROM role_permissions WHERE role_id = :role_id AND permission_id = :permission_id'), {'role_id': 'admin-role', 'permission_id': permission.id}) == 1

    engine.dispose()
