import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import Settings


def migration_url() -> str:
    # Never put credentials into alembic.ini or interpolate them through ConfigParser.
    if value := os.environ.get("MIGRATION_DATABASE_URL"):
        return value
    configured = Settings().migration_database_url
    if configured is None:
        raise RuntimeError("MIGRATION_DATABASE_URL is required; runtime credentials cannot migrate")
    return configured.get_secret_value()


if context.is_offline_mode():
    context.configure(url=migration_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(migration_url(), poolclass=pool.NullPool, hide_parameters=True)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
