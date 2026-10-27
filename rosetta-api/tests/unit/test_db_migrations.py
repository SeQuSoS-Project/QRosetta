"""Schema migrations (db/migrate.py, migrations/): the baseline equals db/models.py, a new
database is created at head, a database from before Alembic (today's, an older one, v1.0.0's)
is brought to the baseline and stamped with its rows kept, an added revision applies, and
concurrent starts do not race."""
import io
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.sql import func

import db.models as models
from db.database import Base
from db.migrate import (BASELINE_REVISION, MIGRATIONS_DIR, SchemaAdoptionError, _baseline_metadata,
                        alembic_config, current_revision, upgrade_database)

API_DIR = Path(__file__).resolve().parents[2]
HEAD = ScriptDirectory.from_config(alembic_config()).get_current_head()


def _engine(tmp_path, name="db.sqlite"):
    return create_engine(f"sqlite:///{tmp_path / name}", connect_args={"check_same_thread": False})


def _diff_against_models(engine):
    with engine.connect() as conn:
        return compare_metadata(MigrationContext.configure(conn), Base.metadata)


def _ddl(metadata, dialect):
    statements = set()
    for table in metadata.sorted_tables:
        statements.add(str(CreateTable(table).compile(dialect=dialect)).strip())
        statements |= {str(CreateIndex(i).compile(dialect=dialect)).strip() for i in table.indexes}
    return statements


@pytest.mark.parametrize("dialect", [sqlite.dialect(), postgresql.dialect()], ids=["sqlite", "postgresql"])
def test_baseline_emits_the_same_ddl_as_the_models(dialect):
    assert _ddl(_baseline_metadata(MIGRATIONS_DIR), dialect) == _ddl(Base.metadata, dialect)


def test_a_new_database_is_created_at_head(tmp_path):
    engine = _engine(tmp_path)
    result = upgrade_database(engine)
    assert result == {"from": None, "to": HEAD, "adopted": None}
    assert set(inspect(engine).get_table_names()) == {"alembic_version", *Base.metadata.tables}
    assert upgrade_database(engine) == {"from": HEAD, "to": HEAD, "adopted": None}


def test_models_and_migrations_agree(tmp_path):
    """Fails when db/models.py changes without a revision in migrations/versions/."""
    engine = _engine(tmp_path)
    upgrade_database(engine)
    assert _diff_against_models(engine) == []


def _seed(engine, *, share_link=True):
    Session = sessionmaker(bind=engine)
    with Session() as db:
        user = models.User(email="kept@example.org", hashed_password="x")
        db.add(user)
        db.flush()
        circuit = models.SavedCircuit(user_id=user.id, name="bell", qasm_string="OPENQASM 2.0;")
        db.add(circuit)
        db.flush()
        run = models.RunHistory(user_id=user.id, circuit_id=circuit.id, s3_object_key="runs/a.json", run_name="r")
        db.add(run)
        db.flush()
        if share_link:
            db.add(models.ShareLink(token_hash="0" * 64, user_id=user.id, run_id=run.id, label="lecture",
                                    expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        db.commit()


def _counts(engine):
    with engine.connect() as conn:
        return {t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                for t in inspect(engine).get_table_names() if t != "alembic_version"}


def test_a_database_from_before_migrations_is_stamped_and_keeps_its_rows(tmp_path):
    engine = _engine(tmp_path)
    Base.metadata.create_all(bind=engine)
    _seed(engine)
    before = _counts(engine)
    assert upgrade_database(engine) == {"from": None, "to": HEAD, "adopted": []}
    assert _counts(engine) == before == {"users": 1, "saved_circuits": 1, "run_histories": 1, "share_links": 1}
    assert _diff_against_models(engine) == []


def test_an_older_schema_gets_its_missing_nullable_columns_and_indexes_before_stamping(tmp_path):
    engine = _engine(tmp_path)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX ix_run_histories_job_id"))
        conn.execute(text("ALTER TABLE share_links DROP COLUMN label"))
        conn.execute(text("ALTER TABLE run_histories DROP COLUMN job_id"))
    result = upgrade_database(engine)
    assert sorted(result["adopted"]) == ["column run_histories.job_id", "column share_links.label",
                                         "index ix_run_histories_job_id"]
    assert result["to"] == HEAD
    assert _diff_against_models(engine) == []


V1 = declarative_base()


class V1User(V1):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    auth_provider = Column(String, default="local", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class V1SavedCircuit(V1):
    __tablename__ = "saved_circuits"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    qasm_string = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class V1RunHistory(V1):
    __tablename__ = "run_histories"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    circuit_id = Column(String(36), ForeignKey("saved_circuits.id"), nullable=True, index=True)
    s3_object_key = Column(String, nullable=False, unique=True, index=True)
    run_name = Column(String, nullable=False, default="Unknown")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def test_a_v1_0_0_database_upgrades_with_its_rows_kept(tmp_path):
    """V1 is rosetta-api/db/models.py at tag v1.0.0: no run_histories.job_id, no share_links."""
    engine = _engine(tmp_path)
    V1.metadata.create_all(bind=engine)
    with sessionmaker(bind=engine)() as db:
        user = V1User(email="v1@example.org", hashed_password="h")
        db.add(user)
        db.flush()
        circuit = V1SavedCircuit(user_id=user.id, name="ghz", qasm_string="OPENQASM 2.0;")
        db.add(circuit)
        db.flush()
        db.add(V1RunHistory(user_id=user.id, circuit_id=circuit.id, s3_object_key="runs/v1.json", run_name="old"))
        db.commit()
    result = upgrade_database(engine)
    assert sorted(result["adopted"]) == ["column run_histories.job_id", "index ix_run_histories_job_id",
                                         "table share_links"]
    assert result["to"] == HEAD
    assert _diff_against_models(engine) == []
    with sessionmaker(bind=engine)() as db:
        run = db.query(models.RunHistory).one()
        assert (run.run_name, run.s3_object_key, run.job_id) == ("old", "runs/v1.json", None)
        assert db.query(models.User).one().email == "v1@example.org"
        db.add(models.ShareLink(token_hash="1" * 64, user_id=run.user_id, run_id=run.id,
                                expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        db.commit()


def test_a_missing_non_nullable_column_is_refused_and_nothing_changes(tmp_path):
    engine = _engine(tmp_path)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR NOT NULL, "
                          "hashed_password VARCHAR, is_active BOOLEAN NOT NULL, created_at DATETIME)"))
    with pytest.raises(SchemaAdoptionError, match="users.auth_provider"):
        upgrade_database(engine)
    assert set(inspect(engine).get_table_names()) == {"users"}


def test_an_added_revision_with_a_nullable_column_applies_and_reverts(tmp_path):
    scripts = tmp_path / "migrations"
    shutil.copytree(MIGRATIONS_DIR, scripts, ignore=shutil.ignore_patterns("__pycache__"))
    (scripts / "versions" / "9999_add_display_name.py").write_text(textwrap.dedent(f'''\
        """Add users.display_name"""
        from alembic import op
        import sqlalchemy as sa

        revision = "9999"
        down_revision = "{HEAD}"
        branch_labels = None
        depends_on = None


        def upgrade():
            with op.batch_alter_table("users") as batch:
                batch.add_column(sa.Column("display_name", sa.String(80), nullable=True))


        def downgrade():
            with op.batch_alter_table("users") as batch:
                batch.drop_column("display_name")
        '''))
    engine = _engine(tmp_path)
    upgrade_database(engine)
    _seed(engine)
    assert upgrade_database(engine, scripts) == {"from": HEAD, "to": "9999", "adopted": None}
    assert "display_name" in {c["name"] for c in inspect(engine).get_columns("users")}
    assert _counts(engine)["users"] == 1
    with engine.begin() as conn:
        command.downgrade(alembic_config(scripts, connection=conn), HEAD)
        assert current_revision(conn) == HEAD
    assert "display_name" not in {c["name"] for c in inspect(engine).get_columns("users")}
    assert _counts(engine)["users"] == 1


_CHILD = """
import os, sys, time
from sqlalchemy import create_engine
from db.migrate import upgrade_database
while not os.path.exists(sys.argv[2]):
    time.sleep(0.005)
print(upgrade_database(create_engine("sqlite:///" + sys.argv[1]))["to"])
"""


@pytest.mark.parametrize("pre_alembic", [False, True], ids=["new", "pre-alembic"])
def test_concurrent_starts_migrate_once(tmp_path, pre_alembic):
    db_path = tmp_path / "shared.sqlite"
    if pre_alembic:
        engine = _engine(tmp_path, "shared.sqlite")
        Base.metadata.create_all(bind=engine)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE share_links DROP COLUMN label"))
        engine.dispose()
    go = tmp_path / "go"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(API_DIR), str(API_DIR.parent / "shared")])}
    children = [subprocess.Popen([sys.executable, "-c", _CHILD, str(db_path), str(go)], cwd=tmp_path, env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
    time.sleep(1.0)
    go.touch()
    outputs = [child.communicate(timeout=120) for child in children]
    assert [child.returncode for child in children] == [0] * 4, [err for _, err in outputs]
    assert [out.strip() for out, _ in outputs] == [HEAD] * 4
    engine = _engine(tmp_path, "shared.sqlite")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all() == [HEAD]
    assert _diff_against_models(engine) == []


def test_offline_postgresql_script_with_an_encoded_password():
    """No PostgreSQL server here: the upgrade is rendered as SQL for the postgresql dialect. The
    URL's `%23` would break a configparser option; it travels in Config.attributes instead."""
    config = alembic_config(url="postgresql://qrosetta:p%23ss%25word@db.example:5432/qrosetta")
    config.output_buffer = io.StringIO()
    command.upgrade(config, "head", sql=True)
    sql = config.output_buffer.getvalue()
    assert "CREATE TABLE users (\n    id SERIAL NOT NULL" in sql
    assert "expires_at TIMESTAMP WITH TIME ZONE NOT NULL" in sql
    assert "CREATE UNIQUE INDEX ix_share_links_token_hash ON share_links (token_hash);" in sql
    assert f"INSERT INTO alembic_version (version_num) VALUES ('{HEAD}')" in sql
    assert sql.rstrip().endswith("COMMIT;")


_STARTUP = """
import json
from sqlalchemy import inspect
from fastapi.testclient import TestClient
import main
from db.database import engine
from db.migrate import current_revision
after_import = sorted(inspect(engine).get_table_names())
with TestClient(main.app):
    with engine.connect() as conn:
        print(json.dumps({"after_import": after_import, "after_startup": current_revision(conn)}))
"""


def _clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("DATABASE_URL", "QROSETTA_JOB_SPILL_DIR") and not k.startswith(("_QROSETTA_TEST_", "PYTEST_"))}
    return {**env, "PYTHONPATH": os.pathsep.join([str(API_DIR), str(API_DIR.parent / "shared")]), **extra}


def test_importing_the_app_does_no_schema_work_and_startup_migrates(tmp_path):
    env = _clean_env(DATABASE_URL=f"sqlite:///{tmp_path / 'startup.sqlite'}",
                     QROSETTA_JOB_SPILL_DIR=str(tmp_path / "spill"))
    out = subprocess.run([sys.executable, "-c", _STARTUP], cwd=API_DIR, env=env, capture_output=True,
                         text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout.strip().splitlines()[-1]) == {"after_import": [], "after_startup": HEAD}


_PROBE = """
import os

def _record():
    with open(os.environ["PROBE_OUT"], "a") as fh:
        fh.write(os.environ["DATABASE_URL"] + " " + os.environ["QROSETTA_JOB_SPILL_DIR"] + "\\n")

def test_a(): _record()
def test_b(): _record()
def test_c(): _record()
def test_d(): _record()
"""


def test_each_xdist_worker_gets_its_own_database_and_spill_directory(tmp_path):
    """xdist workers inherit the controller's environment; the conftest must not hand all of
    them the controller's database, or their startups race on one SQLite file."""
    shutil.copy(Path(__file__).with_name("conftest.py"), tmp_path / "conftest.py")
    (tmp_path / "test_probe.py").write_text(_PROBE)
    out_file = tmp_path / "out.txt"
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-n", "2",
                             "--dist", "each", str(tmp_path / "test_probe.py")],
                            cwd=tmp_path, env=_clean_env(PROBE_OUT=str(out_file)), capture_output=True,
                            text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    pairs = set(out_file.read_text().splitlines())
    assert len(pairs) == 2
    assert len({p.split()[0] for p in pairs}) == len({p.split()[1] for p in pairs}) == 2
