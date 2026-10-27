"""Baseline schema

The tables of db/models.py at 2.0.0.dev0: users, saved_circuits, run_histories, share_links.
db/migrate.py also reads baseline_metadata() to bring a database created before Alembic up to
this revision before stamping it.

Revision ID: 0001
Revises:
Create Date: 2026-10-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def baseline_metadata() -> sa.MetaData:
    metadata = sa.MetaData()
    sa.Table(
        "users", metadata,
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("email", sa.String, unique=True, index=True, nullable=False),
        sa.Column("hashed_password", sa.String, nullable=True),
        sa.Column("auth_provider", sa.String, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    sa.Table(
        "saved_circuits", metadata,
        sa.Column("id", sa.String(36), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("qasm_string", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    sa.Table(
        "run_histories", metadata,
        sa.Column("id", sa.String(36), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("circuit_id", sa.String(36), sa.ForeignKey("saved_circuits.id"), nullable=True, index=True),
        sa.Column("s3_object_key", sa.String, nullable=False, unique=True, index=True),
        sa.Column("run_name", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("job_id", sa.String(36), nullable=True, index=True),
    )
    sa.Table(
        "share_links", metadata,
        sa.Column("id", sa.String(36), primary_key=True, index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("run_histories.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("label", sa.String(100), nullable=True),
    )
    return metadata


def upgrade() -> None:
    baseline_metadata().create_all(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    baseline_metadata().drop_all(bind=op.get_bind(), checkfirst=False)
