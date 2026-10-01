# Database connection and session management.

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

default_db_path = "./data/qa_rosetta.db"
os.makedirs(os.path.dirname(default_db_path), exist_ok=True)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{default_db_path}")

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def add_missing_nullable_columns(metadata, bind) -> list:
    """Add each nullable model column missing from an existing table (create_all creates
    missing tables but never alters existing ones). Returns ``["table.column", ...]``
    added. A missing non-nullable column is left alone, since it needs a real migration."""
    from sqlalchemy import inspect, text
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    added = []
    with bind.begin() as conn:
        for table in metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present or not column.nullable:
                    continue
                ddl = column.type.compile(dialect=bind.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl}'))
                added.append(f"{table.name}.{column.name}")
    return added

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
