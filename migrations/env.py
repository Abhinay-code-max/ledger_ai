"""Alembic environment using the explicit migration-owner DSN."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from ledgerai_backend.assurance import models as assurance_models  # noqa: F401
from ledgerai_backend.core.config import Settings
from ledgerai_backend.database.base import Base
from ledgerai_backend.ingestion import models as ingestion_models  # noqa: F401
from ledgerai_backend.integration import models as integration_models  # noqa: F401
from ledgerai_backend.tenancy import models  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

settings = Settings()
if not settings.migration_dsn:
    raise RuntimeError("LEDGERAI_MIGRATION_DSN is required for migrations")
config.set_main_option(
    "sqlalchemy.url", settings.migration_dsn.get_secret_value().replace("%", "%%")
)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
