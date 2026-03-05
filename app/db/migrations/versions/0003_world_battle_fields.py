"""Add world generation and fast battle fields.

Revision ID: 0003_world_battle_fields
Revises: 0002_perf_indexes
Create Date: 2026-03-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_world_battle_fields"
down_revision = "0002_perf_indexes"
branch_labels = None
depends_on = None


def _has_column(columns: set[str], name: str) -> bool:
    return name in columns


def _ensure_column(table: str, columns: set[str], column: sa.Column) -> None:
    if _has_column(columns, column.name):
        return
    op.add_column(table, column)
    columns.add(column.name)


def _ensure_index(bind: sa.Connection, table: str, name: str, cols: list[str]) -> None:
    inspector = sa.inspect(bind)
    existing = {idx["name"] for idx in inspector.get_indexes(table)}
    if name in existing:
        return
    op.create_index(name, table, cols, unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    session_cols = {c["name"] for c in inspector.get_columns("sessions")}
    _ensure_column("sessions", session_cols, sa.Column("world_seed", sa.String(length=64), nullable=True))
    _ensure_column("sessions", session_cols, sa.Column("world_profile", sa.JSON(), nullable=True))
    _ensure_column("sessions", session_cols, sa.Column("starter_options", sa.JSON(), nullable=True))
    _ensure_column("sessions", session_cols, sa.Column("gym_plan", sa.JSON(), nullable=True))
    _ensure_column(
        "sessions",
        session_cols,
        sa.Column("battle_mode", sa.String(length=20), nullable=False, server_default="fast"),
    )

    turn_cols = {c["name"] for c in inspector.get_columns("turns")}
    _ensure_column("turns", turn_cols, sa.Column("action_options", sa.JSON(), nullable=True))
    _ensure_column("turns", turn_cols, sa.Column("battle_summary", sa.JSON(), nullable=True))

    _ensure_index(bind, "sessions", "ix_sessions_world_seed", ["world_seed"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    session_cols = {c["name"] for c in inspector.get_columns("sessions")}
    turn_cols = {c["name"] for c in inspector.get_columns("turns")}
    session_indexes = {idx["name"] for idx in inspector.get_indexes("sessions")}

    if "ix_sessions_world_seed" in session_indexes:
        op.drop_index("ix_sessions_world_seed", table_name="sessions")

    if "battle_summary" in turn_cols:
        op.drop_column("turns", "battle_summary")
    if "action_options" in turn_cols:
        op.drop_column("turns", "action_options")

    if "battle_mode" in session_cols:
        op.drop_column("sessions", "battle_mode")
    if "gym_plan" in session_cols:
        op.drop_column("sessions", "gym_plan")
    if "starter_options" in session_cols:
        op.drop_column("sessions", "starter_options")
    if "world_profile" in session_cols:
        op.drop_column("sessions", "world_profile")
    if "world_seed" in session_cols:
        op.drop_column("sessions", "world_seed")
