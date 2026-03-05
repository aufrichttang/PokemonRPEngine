"""Add player state fields for session and turns.

Revision ID: 0004_player_state_fields
Revises: 0003_world_battle_fields
Create Date: 2026-03-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_player_state_fields"
down_revision = "0003_world_battle_fields"
branch_labels = None
depends_on = None


def _has_column(columns: set[str], name: str) -> bool:
    return name in columns


def _ensure_column(table: str, columns: set[str], column: sa.Column) -> None:
    if _has_column(columns, column.name):
        return
    op.add_column(table, column)
    columns.add(column.name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    session_cols = {c["name"] for c in inspector.get_columns("sessions")}
    turn_cols = {c["name"] for c in inspector.get_columns("turns")}

    _ensure_column("sessions", session_cols, sa.Column("player_state", sa.JSON(), nullable=True))
    _ensure_column("turns", turn_cols, sa.Column("state_update", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    session_cols = {c["name"] for c in inspector.get_columns("sessions")}
    turn_cols = {c["name"] for c in inspector.get_columns("turns")}

    if "state_update" in turn_cols:
        op.drop_column("turns", "state_update")
    if "player_state" in session_cols:
        op.drop_column("sessions", "player_state")
