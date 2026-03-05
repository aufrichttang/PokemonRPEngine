"""Initial schema for Pokemon RP engine.

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-28
"""

from __future__ import annotations

from alembic import op

from app.db import models  # noqa: F401
from app.db.base import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    Base.metadata.create_all(bind=bind)

    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_memory_chunks_embedding_ivfflat "
            "ON memory_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
        )


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
