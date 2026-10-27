# Alembic environment: migrates the connection db/migrate.py passes in, else DATABASE_URL.

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

import db.models  # noqa: F401  (registers the tables on Base.metadata)
from db.database import SQLALCHEMY_DATABASE_URL, Base

config = context.config
if config.config_file_name is not None and not config.attributes.get("connection"):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

CONFIGURE_OPTIONS = {"target_metadata": Base.metadata, "render_as_batch": True}


def run_migrations_offline() -> None:
    context.configure(url=config.attributes.get("url") or SQLALCHEMY_DATABASE_URL,
                      literal_binds=True, dialect_opts={"paramstyle": "named"}, **CONFIGURE_OPTIONS)
    with context.begin_transaction():
        context.run_migrations()


def _run_on(connection) -> None:
    context.configure(connection=connection, **CONFIGURE_OPTIONS)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run_on(connection)
        return
    engine = create_engine(config.attributes.get("url") or SQLALCHEMY_DATABASE_URL, poolclass=NullPool)
    with engine.begin() as conn:
        _run_on(conn)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
