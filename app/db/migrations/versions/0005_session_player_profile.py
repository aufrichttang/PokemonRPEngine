"""Add player profile column for sessions.

Revision ID: 0005_session_player_profile
Revises: 0004_player_state_fields
Create Date: 2026-03-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_session_player_profile"
down_revision = "0004_player_state_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    session_cols = {c["name"] for c in inspector.get_columns("sessions")}
    if "player_profile" not in session_cols:
        op.add_column("sessions", sa.Column("player_profile", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    session_cols = {c["name"] for c in inspector.get_columns("sessions")}
    if "player_profile" in session_cols:
        op.drop_column("sessions", "player_profile")
