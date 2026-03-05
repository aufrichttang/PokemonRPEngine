"""Add lore/time/faction kernel state and memory time metadata.

Revision ID: 0007_lore_kernel_states
Revises: 0006_v2_game_tables
Create Date: 2026-03-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_lore_kernel_states"
down_revision = "0006_v2_game_tables"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    cols = inspector.get_columns(table_name)
    return any(col.get("name") == column_name for col in cols)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    time_class_enum = sa.Enum(
        "fixed",
        "fragile",
        "unjudged",
        "echo",
        name="time_class",
    )
    protocol_phase_enum = sa.Enum(
        "silent_sampling",
        "interface_fatigue",
        "narrative_stripping",
        "authority_reclamation",
        "silent_recompile",
        name="protocol_phase",
    )

    if _has_table(inspector, "save_slots"):
        with op.batch_alter_table("save_slots") as batch:
            batch.alter_column("schema_version", server_default="3", existing_type=sa.Integer())

    if not _has_table(inspector, "game_slot_lore_state"):
        op.create_table(
            "game_slot_lore_state",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "slot_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("save_slots.id"),
                nullable=False,
                unique=True,
            ),
            sa.Column("global_balance_index", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("human_power_dependency", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("cycle_instability", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("protocol_phase", protocol_phase_enum, nullable=False, server_default="silent_sampling"),
            sa.Column("player_cross_signature_level", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("legendary_alignment", sa.JSON(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
        )
        op.create_index("ix_slot_lore_state_slot", "game_slot_lore_state", ["slot_id"])

    if not _has_table(inspector, "game_slot_time_state"):
        op.create_table(
            "game_slot_time_state",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "slot_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("save_slots.id"),
                nullable=False,
                unique=True,
            ),
            sa.Column("temporal_debt", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("narrative_cohesion", sa.Integer(), nullable=False, server_default="80"),
            sa.Column("judicative_stability", sa.Integer(), nullable=False, server_default="80"),
            sa.Column("compilation_risk", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("phase3_stripping_progress", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
        )
        op.create_index("ix_slot_time_state_slot", "game_slot_time_state", ["slot_id"])

    if not _has_table(inspector, "game_slot_faction_state"):
        op.create_table(
            "game_slot_faction_state",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "slot_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("save_slots.id"),
                nullable=False,
                unique=True,
            ),
            sa.Column("league_central_stability", sa.Integer(), nullable=False, server_default="70"),
            sa.Column("league_public_faction_power", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("league_regional_defiance", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("white_ring_banist", sa.Integer(), nullable=False, server_default="35"),
            sa.Column("white_ring_transitionist", sa.Integer(), nullable=False, server_default="45"),
            sa.Column("white_ring_accelerationist", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("consortium_governance", sa.Integer(), nullable=False, server_default="45"),
            sa.Column("consortium_expansion", sa.Integer(), nullable=False, server_default="35"),
            sa.Column("consortium_substitution", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("grassroots_mutual_aid", sa.Integer(), nullable=False, server_default="45"),
            sa.Column("grassroots_militia", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("grassroots_radicalisation", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("witnesses_intervention", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("witnesses_preservation", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("witnesses_resignation", sa.Integer(), nullable=False, server_default="20"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
        )
        op.create_index("ix_slot_faction_state_slot", "game_slot_faction_state", ["slot_id"])

    if _has_table(inspector, "timeline_events"):
        with op.batch_alter_table("timeline_events") as batch:
            if not _has_column(inspector, "timeline_events", "time_class"):
                batch.add_column(
                    sa.Column("time_class", time_class_enum, nullable=False, server_default="unjudged")
                )
            if not _has_column(inspector, "timeline_events", "source_trust"):
                batch.add_column(
                    sa.Column("source_trust", sa.Float(), nullable=False, server_default="0.6")
                )
            if not _has_column(inspector, "timeline_events", "witness_count"):
                batch.add_column(
                    sa.Column("witness_count", sa.Integer(), nullable=False, server_default="1")
                )
            if not _has_column(inspector, "timeline_events", "narrative_conflict_score"):
                batch.add_column(
                    sa.Column(
                        "narrative_conflict_score",
                        sa.Integer(),
                        nullable=False,
                        server_default="30",
                    )
                )
            if not _has_column(inspector, "timeline_events", "canon_legacy_tags"):
                batch.add_column(
                    sa.Column("canon_legacy_tags", sa.JSON(), nullable=False, server_default="[]")
                )

    if _has_table(inspector, "memory_chunks"):
        with op.batch_alter_table("memory_chunks") as batch:
            if not _has_column(inspector, "memory_chunks", "time_class"):
                batch.add_column(
                    sa.Column("time_class", time_class_enum, nullable=False, server_default="unjudged")
                )
            if not _has_column(inspector, "memory_chunks", "source_trust"):
                batch.add_column(
                    sa.Column("source_trust", sa.Float(), nullable=False, server_default="0.6")
                )
            if not _has_column(inspector, "memory_chunks", "witness_count"):
                batch.add_column(
                    sa.Column("witness_count", sa.Integer(), nullable=False, server_default="1")
                )
            if not _has_column(inspector, "memory_chunks", "narrative_conflict_score"):
                batch.add_column(
                    sa.Column(
                        "narrative_conflict_score",
                        sa.Integer(),
                        nullable=False,
                        server_default="30",
                    )
                )
            if not _has_column(inspector, "memory_chunks", "canon_legacy_tags"):
                batch.add_column(
                    sa.Column("canon_legacy_tags", sa.JSON(), nullable=False, server_default="[]")
                )

    if _has_table(inspector, "timeline_events"):
        existing_idx = {idx["name"] for idx in inspector.get_indexes("timeline_events")}
        if "ix_timeline_time_class" not in existing_idx:
            op.create_index("ix_timeline_time_class", "timeline_events", ["time_class"])

    if _has_table(inspector, "memory_chunks"):
        existing_idx = {idx["name"] for idx in inspector.get_indexes("memory_chunks")}
        if "ix_chunks_time_class" not in existing_idx:
            op.create_index("ix_chunks_time_class", "memory_chunks", ["time_class"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "memory_chunks"):
        existing_idx = {idx["name"] for idx in inspector.get_indexes("memory_chunks")}
        if "ix_chunks_time_class" in existing_idx:
            op.drop_index("ix_chunks_time_class", table_name="memory_chunks")
        with op.batch_alter_table("memory_chunks") as batch:
            for col in (
                "canon_legacy_tags",
                "narrative_conflict_score",
                "witness_count",
                "source_trust",
                "time_class",
            ):
                if _has_column(inspector, "memory_chunks", col):
                    batch.drop_column(col)

    if _has_table(inspector, "timeline_events"):
        existing_idx = {idx["name"] for idx in inspector.get_indexes("timeline_events")}
        if "ix_timeline_time_class" in existing_idx:
            op.drop_index("ix_timeline_time_class", table_name="timeline_events")
        with op.batch_alter_table("timeline_events") as batch:
            for col in (
                "canon_legacy_tags",
                "narrative_conflict_score",
                "witness_count",
                "source_trust",
                "time_class",
            ):
                if _has_column(inspector, "timeline_events", col):
                    batch.drop_column(col)

    for idx_name, table in [
        ("ix_slot_faction_state_slot", "game_slot_faction_state"),
        ("ix_slot_time_state_slot", "game_slot_time_state"),
        ("ix_slot_lore_state_slot", "game_slot_lore_state"),
    ]:
        if _has_table(inspector, table):
            existing_idx = {idx["name"] for idx in inspector.get_indexes(table)}
            if idx_name in existing_idx:
                op.drop_index(idx_name, table_name=table)

    for table in (
        "game_slot_faction_state",
        "game_slot_time_state",
        "game_slot_lore_state",
    ):
        if _has_table(inspector, table):
            op.drop_table(table)

    if _has_table(inspector, "save_slots"):
        with op.batch_alter_table("save_slots") as batch:
            batch.alter_column("schema_version", server_default="2", existing_type=sa.Integer())
