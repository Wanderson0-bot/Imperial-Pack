from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.database.base import Base
from app.database import models  # noqa: F401 - load model metadata for Alembic


config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

url = get_settings().database_url

if not url:
    raise RuntimeError('DATABASE_URL must be configured before running migrations.')

config.set_main_option('sqlalchemy.url', url.replace('%', '%%'))

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    """
    Ignore a PostgreSQL expression-index representation difference that is
    semantically equivalent to the current SQLAlchemy model.

    PostgreSQL stores:
        lower(TRIM(BOTH FROM name))

    while SQLAlchemy/Alembic generates:
        lower(trim(name))
    """
    if type_ == 'index' and name == 'uq_suppliers_normalized_name':
        return False

    return True


def run_migrations_offline():
    context.configure(
        url=config.get_main_option('sqlalchemy.url'),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()