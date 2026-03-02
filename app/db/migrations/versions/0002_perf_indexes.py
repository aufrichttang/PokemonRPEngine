"""Add performance indexes for login/session workloads.

Revision ID: 0002_perf_indexes
Revises: 0001_initial
Create Date: 2026-02-28
"""

from __future__ import annotations

from alembic import op

revision = "0002_perf_indexes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sessions_user_deleted_updated "
        "ON sessions (user_id, deleted, updated_at);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_turns_session_turn_index "
        "ON turns (session_id, turn_index);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_timeline_session_created "
        "ON timeline_events (session_id, created_at);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_timeline_session_created;")
    op.execute("DROP INDEX IF EXISTS ix_turns_session_turn_index;")
    op.execute("DROP INDEX IF EXISTS ix_sessions_user_deleted_updated;")
