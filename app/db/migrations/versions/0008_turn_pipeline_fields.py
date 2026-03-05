"""Add v2 turn pipeline status/idempotency/timing fields.

Revision ID: 0008_turn_pipeline_fields
Revises: 0007_lore_kernel_states
Create Date: 2026-03-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_turn_pipeline_fields"
down_revision = "0007_lore_kernel_states"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "session_turns_v2"):
        return

    with op.batch_alter_table("session_turns_v2") as batch:
        if not _has_column(inspector, "session_turns_v2", "client_turn_id"):
            batch.add_column(sa.Column("client_turn_id", sa.String(length=64), nullable=True))
        if not _has_column(inspector, "session_turns_v2", "status"):
            batch.add_column(
                sa.Column("status", sa.String(length=20), nullable=False, server_default="done")
            )
        if not _has_column(inspector, "session_turns_v2", "planner_payload"):
            batch.add_column(sa.Column("planner_payload", sa.JSON(), nullable=True))
        if not _has_column(inspector, "session_turns_v2", "primary_text"):
            batch.add_column(sa.Column("primary_text", sa.Text(), nullable=True))
        if not _has_column(inspector, "session_turns_v2", "detail_text"):
            batch.add_column(sa.Column("detail_text", sa.Text(), nullable=True))
        if not _has_column(inspector, "session_turns_v2", "first_interactive_ms"):
            batch.add_column(sa.Column("first_interactive_ms", sa.Integer(), nullable=True))
        if not _has_column(inspector, "session_turns_v2", "first_primary_ms"):
            batch.add_column(sa.Column("first_primary_ms", sa.Integer(), nullable=True))
        if not _has_column(inspector, "session_turns_v2", "done_ms"):
            batch.add_column(sa.Column("done_ms", sa.Integer(), nullable=True))

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("session_turns_v2")}
    if "ix_session_turns_v2_slot_status" not in existing_indexes:
        op.create_index(
            "ix_session_turns_v2_slot_status",
            "session_turns_v2",
            ["slot_id", "status"],
        )
    if "ix_session_turns_v2_slot_client_turn" not in existing_indexes:
        op.create_index(
            "ix_session_turns_v2_slot_client_turn",
            "session_turns_v2",
            ["slot_id", "client_turn_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "session_turns_v2"):
        return

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("session_turns_v2")}
    if "ix_session_turns_v2_slot_client_turn" in existing_indexes:
        op.drop_index("ix_session_turns_v2_slot_client_turn", table_name="session_turns_v2")
    if "ix_session_turns_v2_slot_status" in existing_indexes:
        op.drop_index("ix_session_turns_v2_slot_status", table_name="session_turns_v2")

    with op.batch_alter_table("session_turns_v2") as batch:
        for col in (
            "done_ms",
            "first_primary_ms",
            "first_interactive_ms",
            "detail_text",
            "primary_text",
            "planner_payload",
            "status",
            "client_turn_id",
        ):
            if _has_column(inspector, "session_turns_v2", col):
                batch.drop_column(col)
