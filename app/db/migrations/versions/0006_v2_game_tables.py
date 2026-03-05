"""Add V2 game domain tables.

Revision ID: 0006_v2_game_tables
Revises: 0005_session_player_profile
Create Date: 2026-03-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_v2_game_tables"
down_revision = "0005_session_player_profile"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "save_slots"):
        op.create_table(
            "save_slots",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column(
                "session_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("sessions.id"),
                nullable=False,
                unique=True,
            ),
            sa.Column("slot_name", sa.String(length=120), nullable=False),
            sa.Column("schema_version", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("world_seed", sa.String(length=64), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
        )
        op.create_index("ix_save_slots_user_updated", "save_slots", ["user_id", "updated_at"])

    if not _has_table(inspector, "player_profiles_v2"):
        op.create_table(
            "player_profiles_v2",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "slot_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("save_slots.id"),
                nullable=False,
                unique=True,
            ),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("gender", sa.String(length=20), nullable=False),
            sa.Column("age", sa.Integer(), nullable=False, server_default="18"),
            sa.Column("height_cm", sa.Integer(), nullable=False, server_default="170"),
            sa.Column("appearance", sa.Text(), nullable=True),
            sa.Column("personality", sa.Text(), nullable=True),
            sa.Column("background", sa.Text(), nullable=True),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("backstory", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
        )

    if not _has_table(inspector, "party_slots"):
        op.create_table(
            "party_slots",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("slot_id", sa.Uuid(as_uuid=True), sa.ForeignKey("save_slots.id"), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("pokemon_slug", sa.String(length=120), nullable=False),
            sa.Column("pokemon_name_zh", sa.String(length=120), nullable=False),
            sa.Column("level", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("hp_text", sa.String(length=60), nullable=True),
            sa.Column("status_text", sa.String(length=120), nullable=True),
            sa.Column("types", sa.JSON(), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
            sa.UniqueConstraint("slot_id", "position", name="uq_party_slot_position"),
        )
        op.create_index("ix_party_slots_slot_position", "party_slots", ["slot_id", "position"])

    if not _has_table(inspector, "storage_box_entries"):
        op.create_table(
            "storage_box_entries",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("slot_id", sa.Uuid(as_uuid=True), sa.ForeignKey("save_slots.id"), nullable=False),
            sa.Column("box_code", sa.String(length=20), nullable=False, server_default="BOX-1"),
            sa.Column("pokemon_slug", sa.String(length=120), nullable=False),
            sa.Column("pokemon_name_zh", sa.String(length=120), nullable=False),
            sa.Column("level", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("types", sa.JSON(), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
        )
        op.create_index("ix_storage_box_slot", "storage_box_entries", ["slot_id"])

    if not _has_table(inspector, "inventory_items"):
        op.create_table(
            "inventory_items",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("slot_id", sa.Uuid(as_uuid=True), sa.ForeignKey("save_slots.id"), nullable=False),
            sa.Column("category", sa.String(length=40), nullable=False),
            sa.Column("item_name_zh", sa.String(length=120), nullable=False),
            sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
            sa.UniqueConstraint("slot_id", "category", "item_name_zh", name="uq_inventory_item"),
        )
        op.create_index("ix_inventory_slot_category", "inventory_items", ["slot_id", "category"])

    if not _has_table(inspector, "story_progress_v2"):
        op.create_table(
            "story_progress_v2",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "slot_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("save_slots.id"),
                nullable=False,
                unique=True,
            ),
            sa.Column("act_index", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("chapter_index", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("objective", sa.Text(), nullable=False, server_default="推进主线"),
            sa.Column("objective_status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("turns_in_chapter", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("risk_level", sa.String(length=20), nullable=False, server_default="medium"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
        )
        op.create_index("ix_story_progress_slot", "story_progress_v2", ["slot_id"])

    if not _has_table(inspector, "chapter_states"):
        op.create_table(
            "chapter_states",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("slot_id", sa.Uuid(as_uuid=True), sa.ForeignKey("save_slots.id"), nullable=False),
            sa.Column("chapter_index", sa.Integer(), nullable=False),
            sa.Column("act_index", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("objective", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("core_conflict", sa.Text(), nullable=True),
            sa.Column("sacrifice_cost", sa.Text(), nullable=True),
            sa.Column("reward", sa.Text(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
            sa.UniqueConstraint("slot_id", "chapter_index", name="uq_chapter_state_slot_chapter"),
        )
        op.create_index("ix_chapter_states_slot", "chapter_states", ["slot_id"])

    if not _has_table(inspector, "romance_routes"):
        op.create_table(
            "romance_routes",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("slot_id", sa.Uuid(as_uuid=True), sa.ForeignKey("save_slots.id"), nullable=False),
            sa.Column("route_tag", sa.String(length=40), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("role", sa.String(length=120), nullable=False),
            sa.Column("trait", sa.Text(), nullable=True),
            sa.Column("route_hint", sa.Text(), nullable=True),
            sa.Column("affection", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("route_state", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
            sa.UniqueConstraint("slot_id", "route_tag", name="uq_romance_route_slot_tag"),
        )
        op.create_index("ix_romance_routes_slot", "romance_routes", ["slot_id"])

    if not _has_table(inspector, "legendary_states"):
        op.create_table(
            "legendary_states",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("slot_id", sa.Uuid(as_uuid=True), sa.ForeignKey("save_slots.id"), nullable=False),
            sa.Column("slug_id", sa.String(length=120), nullable=False),
            sa.Column("name_zh", sa.String(length=120), nullable=False),
            sa.Column("domain", sa.String(length=120), nullable=True),
            sa.Column("stance", sa.String(length=40), nullable=True),
            sa.Column("risk_level", sa.String(length=20), nullable=True),
            sa.Column("seal_state", sa.String(length=20), nullable=False, server_default="unstable"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
            sa.UniqueConstraint("slot_id", "slug_id", name="uq_legendary_state_slot_slug"),
        )
        op.create_index("ix_legendary_states_slot", "legendary_states", ["slot_id"])

    if not _has_table(inspector, "world_maps_v2"):
        op.create_table(
            "world_maps_v2",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "slot_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("save_slots.id"),
                nullable=False,
                unique=True,
            ),
            sa.Column("map_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("width", sa.Integer(), nullable=False, server_default="36"),
            sa.Column("height", sa.Integer(), nullable=False, server_default="24"),
            sa.Column("seed", sa.String(length=64), nullable=True),
            sa.Column("current_node_id", sa.String(length=64), nullable=True),
            sa.Column("visited_node_ids", sa.JSON(), nullable=True),
            sa.Column("biomes", sa.JSON(), nullable=True),
            sa.Column("chapter_route", sa.JSON(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
        )
        op.create_index("ix_world_maps_slot", "world_maps_v2", ["slot_id"])

    if not _has_table(inspector, "map_nodes_v2"):
        op.create_table(
            "map_nodes_v2",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("world_map_id", sa.Uuid(as_uuid=True), sa.ForeignKey("world_maps_v2.id"), nullable=False),
            sa.Column("node_id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("x", sa.Integer(), nullable=False),
            sa.Column("y", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=40), nullable=False),
            sa.Column("gym_type", sa.String(length=40), nullable=True),
            sa.Column("domain", sa.String(length=40), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.UniqueConstraint("world_map_id", "node_id", name="uq_world_map_node"),
        )
        op.create_index("ix_map_nodes_world_map", "map_nodes_v2", ["world_map_id"])

    if not _has_table(inspector, "map_edges_v2"):
        op.create_table(
            "map_edges_v2",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("world_map_id", sa.Uuid(as_uuid=True), sa.ForeignKey("world_maps_v2.id"), nullable=False),
            sa.Column("from_node_id", sa.String(length=64), nullable=False),
            sa.Column("to_node_id", sa.String(length=64), nullable=False),
            sa.Column("edge_type", sa.String(length=20), nullable=False, server_default="road"),
            sa.Column("meta", sa.JSON(), nullable=True),
        )
        op.create_index("ix_map_edges_world_map", "map_edges_v2", ["world_map_id"])

    if not _has_table(inspector, "session_turns_v2"):
        op.create_table(
            "session_turns_v2",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("slot_id", sa.Uuid(as_uuid=True), sa.ForeignKey("save_slots.id"), nullable=False),
            sa.Column("source_turn_id", sa.Uuid(as_uuid=True), sa.ForeignKey("turns.id"), nullable=True),
            sa.Column("turn_index", sa.Integer(), nullable=False),
            sa.Column("user_text", sa.Text(), nullable=False),
            sa.Column("assistant_text", sa.Text(), nullable=False),
            sa.Column("narrative_primary", sa.Text(), nullable=True),
            sa.Column("narrative_detail", sa.Text(), nullable=True),
            sa.Column("action_options", sa.JSON(), nullable=True),
            sa.Column("battle_summary", sa.JSON(), nullable=True),
            sa.Column("state_snapshot", sa.JSON(), nullable=True),
            sa.Column("provider_latency_ms", sa.Integer(), nullable=True),
            sa.Column("token_usage", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("slot_id", "turn_index", name="uq_session_turn_v2_slot_turn"),
        )
        op.create_index("ix_session_turns_v2_slot", "session_turns_v2", ["slot_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for idx_name, table in [
        ("ix_session_turns_v2_slot", "session_turns_v2"),
        ("ix_map_edges_world_map", "map_edges_v2"),
        ("ix_map_nodes_world_map", "map_nodes_v2"),
        ("ix_world_maps_slot", "world_maps_v2"),
        ("ix_legendary_states_slot", "legendary_states"),
        ("ix_romance_routes_slot", "romance_routes"),
        ("ix_chapter_states_slot", "chapter_states"),
        ("ix_story_progress_slot", "story_progress_v2"),
        ("ix_inventory_slot_category", "inventory_items"),
        ("ix_storage_box_slot", "storage_box_entries"),
        ("ix_party_slots_slot_position", "party_slots"),
        ("ix_save_slots_user_updated", "save_slots"),
    ]:
        if _has_table(inspector, table):
            op.drop_index(idx_name, table_name=table)

    for table in [
        "session_turns_v2",
        "map_edges_v2",
        "map_nodes_v2",
        "world_maps_v2",
        "legendary_states",
        "romance_routes",
        "chapter_states",
        "story_progress_v2",
        "inventory_items",
        "storage_box_entries",
        "party_slots",
        "player_profiles_v2",
        "save_slots",
    ]:
        if _has_table(inspector, table):
            op.drop_table(table)
