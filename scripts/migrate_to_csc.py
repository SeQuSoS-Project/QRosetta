# Migration script for transitioning to CSC environment.

"""
Standalone Python migration script to securely move existing records
from the local SQLite database to the CSC Pukki instance, and mock S3 storage
files to the CSC Allas bucket.
"""
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus, urlparse, urlunparse

try:
    from sqlalchemy import create_engine, MetaData, select, inspect
    from sqlalchemy.dialects.postgresql import insert
except ImportError:
    print("Error: SQLAlchemy is not installed. Please install it with: pip install sqlalchemy")
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2-binary is not installed. Please install it with: pip install psycopg2-binary")
    sys.exit(1)

try:
    import boto3
except ImportError:
    print("Error: boto3 is not installed. Please install it with: pip install boto3")
    sys.exit(1)

def encode_db_url(url: str) -> str:
    """Safely URL-encodes the password component if it contains a `#` or other unsafe chars."""
    if not url or "://" not in url:
        return url

    schema_part, rest = url.split("://", 1)
    if "@" not in rest:
        return url

    userpass, hostdb = rest.split("@", 1)
    if ":" not in userpass:
        return url

    user, password = userpass.split(":", 1)

    if "%" not in password:
        password = quote_plus(password)

    return f"{schema_part}://{user}:{password}@{hostdb}"

def sync_database():
    print("--- Starting Database Sync ---")

    local_db_path = Path("./rosetta-api/qa_rosetta.db")
    local_db_url = f"sqlite:///{local_db_path.absolute()}"
    raw_remote_db_url = os.environ.get("DATABASE_URL")

    if not raw_remote_db_url:
        print("Error: DATABASE_URL environment variable is exactly required.")
        sys.exit(1)

    remote_db_url = encode_db_url(raw_remote_db_url)
    if not remote_db_url.endswith("/qrosetta") and not remote_db_url.endswith("/qrosetta?"):
        print(f"Warning: DATABASE_URL does not seem to point to the 'qrosetta' database: {remote_db_url}")

    print(f"Checking Local Database: {local_db_path}")
    if not local_db_path.exists():
        print(f"Error: Local SQLite DB not found at {local_db_path}")
        sys.exit(1)

    file_size_bytes = local_db_path.stat().st_size
    print(f"Local SQLite DB found. Size: {file_size_bytes} bytes")
    if file_size_bytes == 0:
        print("Error: Local SQLite DB is completely empty (0 bytes).")
        sys.exit(1)

    print(f"Connecting to local SQLite...")
    local_engine = create_engine(local_db_url)

    print("Connecting to remote PostgreSQL...")
    remote_engine = create_engine(remote_db_url)

    local_meta = MetaData()
    remote_meta = MetaData()

    inspector = inspect(local_engine)
    available_tables = inspector.get_table_names()
    tables_to_sync = ["users", "saved_circuits", "run_histories"]

    print(f"Available tables in local SQLite: {available_tables}")

    with local_engine.connect() as local_conn, remote_engine.connect() as remote_conn:

        remote_meta.reflect(bind=remote_engine)
        local_meta.reflect(bind=local_engine)

        for table_name in tables_to_sync:
            print(f"\n> Processing table: {table_name}")

            if table_name not in available_tables:
                print(f"  Warning: Table {table_name} not found in local DB. Skipping.")
                continue

            if table_name not in remote_meta.tables:
                print(f"  Warning: Table {table_name} not found in remote DB. Skipping.")
                continue

            local_table = local_meta.tables[table_name]
            remote_table = remote_meta.tables[table_name]

            result = local_conn.execute(select(local_table))

            if hasattr(result, "mappings"):
                rows = result.mappings().fetchall()
            else:
                rows = [dict(r) for r in result]

            if not rows:
                print(f"  No records found in local table {table_name}. Skipping.")
                continue

            print(f"  Found {len(rows)} records in local table {table_name}. Upserting to remote...")

            success_count = 0
            pk_cols = [c.name for c in remote_table.primary_key.columns]

            if not pk_cols:

                print(f"  Warning: No primary key found for {table_name}. Cannot upsert safely. Attempting generic insert.")
                for row_repr in rows:
                    row_dict = dict(row_repr)
                    try:
                        remote_conn.execute(remote_table.insert().values(row_dict))
                        if hasattr(remote_conn, "commit"):
                            remote_conn.commit()
                        success_count += 1
                        print("    Inserted record without PK constraint.")
                    except Exception as e:
                        print(f"    Failed to insert record: {e}")
                        if hasattr(remote_conn, "rollback"):
                            remote_conn.rollback()
            else:

                for row_repr in rows:
                    row_dict = dict(row_repr)
                    try:
                        stmt = insert(remote_table).values(row_dict)
                        update_dict = {c.name: c for c in stmt.excluded if not c.primary_key}

                        if update_dict:
                            stmt = stmt.on_conflict_do_update(
                                index_elements=pk_cols,
                                set_=update_dict
                            )
                        else:
                            stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)

                        remote_conn.execute(stmt)
                        if hasattr(remote_conn, "commit"):
                            remote_conn.commit()
                        success_count += 1
                        pk_ident = {k: row_dict[k] for k in pk_cols if k in row_dict}
                        print(f"    Upserted record with pk: {pk_ident}")
                    except Exception as e:
                        pk_ident = {k: row_dict.get(k) for k in pk_cols}
                        print(f"    Failed to upsert record with pk: {pk_ident} -> {e}")
                        if hasattr(remote_conn, "rollback"):
                            remote_conn.rollback()

            print(f"  Successfully processed {success_count}/{len(rows)} records for {table_name}.")

    print("\n--- Database Sync Complete ---")

def sync_object_storage():
    print("\n--- Starting Object Storage Sync ---")

    s3_access_key = os.environ.get("S3_ACCESS_KEY")
    s3_secret_key = os.environ.get("S3_SECRET_KEY")
    s3_bucket_name = os.environ.get("S3_BUCKET_NAME")

    if not all([s3_access_key, s3_secret_key, s3_bucket_name]):
        print("Error: S3_ACCESS_KEY, S3_SECRET_KEY, and S3_BUCKET_NAME environment variables are required.")
        sys.exit(1)

    endpoint_url = "https://a3s.fi"

    print(f"Connecting to S3 endpoint: {endpoint_url}")
    print(f"Target Bucket: {s3_bucket_name}")

    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=s3_access_key,
        aws_secret_access_key=s3_secret_key,
        region_name="us-east-1"
    )

    local_dir = Path("./rosetta-api/s3_storage_mock/")

    if not local_dir.exists() or not local_dir.is_dir():
        print(f"Notice: Local mock storage directory {local_dir} not found. Skipping S3 object sync.")
        return

    print(f"Scanning directory: {local_dir}")
    file_count = 0
    success_count = 0

    for file_path in local_dir.rglob("*.json"):
        if not file_path.is_file():
            continue

        file_count += 1
        s3_key = file_path.relative_to(local_dir).as_posix()

        print(f"  Uploading {file_path} -> s3://{s3_bucket_name}/{s3_key}")
        try:
            s3_client.upload_file(str(file_path), s3_bucket_name, s3_key)
            success_count += 1
            print("    Success.")
        except Exception as e:
            print(f"    Failed to upload {file_path}: {e}")

    print(f"--- Object Storage Sync Complete ({success_count}/{file_count} files) ---")

if __name__ == "__main__":
    current_dir = os.path.basename(os.getcwd())
    if current_dir != "qsimulators":
        print("Warning: Script is not run from the 'qsimulators' root directory. S3 paths or SQLite paths might fail.\n")

    try:
        sync_database()
        sync_object_storage()
        print("\nMigration process finished successfully.")
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nMigration interrupted by user.")
        sys.exit(1)
