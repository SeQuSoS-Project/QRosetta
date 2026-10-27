# Schema migrations at startup: brings an unversioned database to the baseline, then `upgrade head`.

import contextlib
import fcntl
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
BASELINE_REVISION = "0001"
PG_ADVISORY_LOCK_KEY = 0x51_52_4F_53_45_54_54_41


class SchemaAdoptionError(RuntimeError):
    """An unversioned database lacks a column the baseline cannot add (non-nullable)."""


def alembic_config(script_location: Path = MIGRATIONS_DIR, *, url: str | None = None,
                   connection: Connection | None = None) -> Config:
    """A Config with no ini file; the URL travels in attributes, never through configparser,
    so URL-encoded passwords (`%23`) are passed through unchanged."""
    config = Config()
    config.set_main_option("script_location", str(script_location).replace("%", "%%"))
    if url is not None:
        config.attributes["url"] = url
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def _sqlite_lock_path(engine: Engine) -> str | None:
    database = engine.url.database
    if engine.dialect.name != "sqlite" or not database or database == ":memory:" or database.startswith("file:"):
        return None
    return os.path.abspath(database) + ".migrate-lock"


@contextlib.contextmanager
def _migration_transaction(engine: Engine):
    """One transaction per process that migrates; other processes wait for it. SQLite: an
    exclusive flock on a file beside the database (the database file itself is never opened,
    which would drop SQLite's own POSIX locks). PostgreSQL: a transaction-scoped advisory lock."""
    lock_path = _sqlite_lock_path(engine)
    with contextlib.ExitStack() as stack:
        if lock_path is not None:
            fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
            stack.callback(os.close, fd)
            fcntl.flock(fd, fcntl.LOCK_EX)
            stack.callback(fcntl.flock, fd, fcntl.LOCK_UN)
        with engine.begin() as connection:
            if engine.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": PG_ADVISORY_LOCK_KEY})
            yield connection


def _baseline_metadata(script_location: Path):
    script = ScriptDirectory.from_config(alembic_config(script_location))
    return script.get_revision(BASELINE_REVISION).module.baseline_metadata()


def adopt_unversioned(connection: Connection, script_location: Path = MIGRATIONS_DIR) -> list[str]:
    """Bring a database created before Alembic (create_all, any release since v1.0.0) up to the
    baseline: create its missing tables, nullable columns and indexes. Returns what it added.
    A missing non-nullable column raises SchemaAdoptionError before anything is changed."""
    baseline = _baseline_metadata(script_location)
    inspector = inspect(connection)
    existing = set(inspector.get_table_names())
    missing_tables = [t for t in baseline.sorted_tables if t.name not in existing]
    missing_columns, missing_indexes = [], []
    for table in baseline.sorted_tables:
        if table.name not in existing:
            continue
        present = {c["name"] for c in inspector.get_columns(table.name)}
        missing_columns += [(table, c) for c in table.columns if c.name not in present]
        indexed = {i["name"] for i in inspector.get_indexes(table.name)}
        missing_indexes += [i for i in table.indexes if i.name not in indexed]
    required = [f"{t.name}.{c.name}" for t, c in missing_columns if not c.nullable]
    if required:
        raise SchemaAdoptionError("The database predates schema migrations and lacks the non-nullable "
                                  f"column(s) {', '.join(required)}; it cannot be brought to the baseline.")
    added = []
    for table in missing_tables:
        table.create(bind=connection)
        added.append(f"table {table.name}")
    preparer = connection.dialect.identifier_preparer
    for table, column in missing_columns:
        ddl = column.type.compile(dialect=connection.dialect)
        connection.execute(text(f"ALTER TABLE {preparer.quote(table.name)} "
                                f"ADD COLUMN {preparer.quote(column.name)} {ddl}"))
        added.append(f"column {table.name}.{column.name}")
    for index in missing_indexes:
        index.create(bind=connection)
        added.append(f"index {index.name}")
    return added


def _is_unversioned_app_database(connection: Connection, baseline) -> bool:
    tables = set(inspect(connection).get_table_names())
    return "alembic_version" not in tables and bool(tables & set(baseline.tables))


def current_revision(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()


def upgrade_database(engine: Engine, script_location: Path = MIGRATIONS_DIR) -> dict:
    """Upgrade to head under the migration lock. Returns {"from", "to", "adopted"}: the revision
    before (None for a new or unversioned database), the revision after, and what adoption added
    (None when the database was not an unversioned one)."""
    with _migration_transaction(engine) as connection:
        before = current_revision(connection)
        adopted = None
        if _is_unversioned_app_database(connection, _baseline_metadata(script_location)):
            adopted = adopt_unversioned(connection, script_location)
            command.stamp(alembic_config(script_location, connection=connection), BASELINE_REVISION)
        command.upgrade(alembic_config(script_location, connection=connection), "head")
        return {"from": before, "to": current_revision(connection), "adopted": adopted}


if __name__ == "__main__":
    from db.database import engine
    from qrosetta_commons.helpers import get_logger
    get_logger("rosetta-db").info(f"Database migration: {upgrade_database(engine)}")
