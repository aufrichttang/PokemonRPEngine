import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover

    class Vector(JSON):
        def __init__(self, _dim: int) -> None:
            super().__init__()


JSONType = JSON


class UserRole(enum.StrEnum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"
    user = "user"


class CanonLevel(enum.StrEnum):
    confirmed = "confirmed"
    implied = "implied"
    pending = "pending"
    conflict = "conflict"


class ProtocolPhase(enum.StrEnum):
    silent_sampling = "silent_sampling"
    interface_fatigue = "interface_fatigue"
    narrative_stripping = "narrative_stripping"
    authority_reclamation = "authority_reclamation"
    silent_recompile = "silent_recompile"


class TimeClass(enum.StrEnum):
    fixed = "fixed"
    fragile = "fragile"
    unjudged = "unjudged"
    echo = "echo"


class ThreadStatus(enum.StrEnum):
    open = "open"
    resolved = "resolved"


class SourceKind(enum.StrEnum):
    pokemon = "pokemon"
    move = "move"
    ability = "ability"
    item = "item"
    type_chart = "type_chart"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.user)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), default="新会话")
    world_template_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    world_seed: Mapped[str | None] = mapped_column(String(64), nullable=True)
    canon_gen: Mapped[int] = mapped_column(Integer, default=9, nullable=False)
    canon_game: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custom_lore_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    world_profile: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    player_profile: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    starter_options: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType, nullable=True)
    gym_plan: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType, nullable=True)
    player_state: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    battle_mode: Mapped[str] = mapped_column(String(20), default="fast", nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship("User", back_populates="sessions")
    turns: Mapped[list["Turn"]] = relationship("Turn", back_populates="session")


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = (UniqueConstraint("session_id", "turn_index", name="uq_session_turn_index"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sessions.id"), nullable=False
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    user_text: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_text: Mapped[str] = mapped_column(Text, nullable=False)
    provider_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    action_options: Mapped[list[dict[str, str]] | None] = mapped_column(JSONType, nullable=True)
    battle_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    state_update: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[Session] = relationship("Session", back_populates="turns")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sessions.id"), nullable=False
    )
    turn_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("turns.id"), nullable=False
    )
    in_world_time: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    actors: Mapped[list[str]] = mapped_column(JSONType, default=list)
    items: Mapped[list[str]] = mapped_column(JSONType, default=list)
    event_text: Mapped[str] = mapped_column(Text, nullable=False)
    consequence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    canon_level: Mapped[CanonLevel] = mapped_column(
        Enum(CanonLevel, name="canon_level"), nullable=False
    )
    time_class: Mapped[TimeClass] = mapped_column(
        Enum(TimeClass, name="time_class"),
        nullable=False,
        default=TimeClass.unjudged,
    )
    source_trust: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)
    witness_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    narrative_conflict_score: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    canon_legacy_tags: Mapped[list[str]] = mapped_column(JSONType, default=list)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryChunk(Base):
    __tablename__ = "memory_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sessions.id"), nullable=False
    )
    turn_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("turns.id"), nullable=False
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    time_class: Mapped[TimeClass] = mapped_column(
        Enum(TimeClass, name="time_class"),
        nullable=False,
        default=TimeClass.unjudged,
    )
    source_trust: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)
    witness_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    narrative_conflict_score: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    canon_legacy_tags: Mapped[list[str]] = mapped_column(JSONType, default=list)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OpenThread(Base):
    __tablename__ = "open_threads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sessions.id"), nullable=False
    )
    status: Mapped[ThreadStatus] = mapped_column(
        Enum(ThreadStatus, name="thread_status"), default=ThreadStatus.open
    )
    thread_text: Mapped[str] = mapped_column(Text, nullable=False)
    related_entities: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sessions.id"), nullable=False
    )
    turn_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("turns.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CanonPokemon(Base):
    __tablename__ = "canon_pokemon"
    __table_args__ = (UniqueConstraint("slug_id", "generation", name="uq_canon_pokemon_slug_gen"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dex_no: Mapped[int] = mapped_column(Integer, nullable=False)
    slug_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONType, default=list)
    form: Mapped[str | None] = mapped_column(String(120), nullable=True)
    types: Mapped[list[str]] = mapped_column(JSONType, default=list)
    base_stats: Mapped[dict[str, int]] = mapped_column(JSONType, default=dict)
    abilities: Mapped[list[str]] = mapped_column(JSONType, default=list)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_version: Mapped[str] = mapped_column(String(120), nullable=False)


class CanonMove(Base):
    __tablename__ = "canon_moves"
    __table_args__ = (UniqueConstraint("slug_id", "generation", name="uq_canon_move_slug_gen"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONType, default=list)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    power: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accuracy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    effect_short: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    game: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_version: Mapped[str] = mapped_column(String(120), nullable=False)


class CanonAbility(Base):
    __tablename__ = "canon_abilities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONType, default=list)
    effect_short: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_version: Mapped[str] = mapped_column(String(120), nullable=False)


class CanonItem(Base):
    __tablename__ = "canon_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONType, default=list)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    effect_short: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_version: Mapped[str] = mapped_column(String(120), nullable=False)


class CanonTypeChart(Base):
    __tablename__ = "canon_type_chart"
    __table_args__ = (UniqueConstraint("atk_type", "def_type", name="uq_type_chart_pair"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    atk_type: Mapped[str] = mapped_column(String(40), nullable=False)
    def_type: Mapped[str] = mapped_column(String(40), nullable=False)
    multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_version: Mapped[str] = mapped_column(String(120), nullable=False)


class CanonEvolution(Base):
    __tablename__ = "canon_evolutions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    to_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    method: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    game: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_version: Mapped[str] = mapped_column(String(120), nullable=False)


class CanonLearnset(Base):
    __tablename__ = "canon_learnsets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pokemon_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    move_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    learn_method: Mapped[str] = mapped_column(String(120), nullable=False)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tm_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tutor: Mapped[bool] = mapped_column(Boolean, default=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    game: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_version: Mapped[str] = mapped_column(String(120), nullable=False)


class SaveSlot(Base):
    __tablename__ = "save_slots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sessions.id"), nullable=False, unique=True
    )
    slot_name: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    world_seed: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PlayerProfileV2(Base):
    __tablename__ = "player_profiles_v2"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("save_slots.id"), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False, default=18)
    height_cm: Mapped[int] = mapped_column(Integer, nullable=False, default=170)
    appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    background: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    backstory: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PartySlot(Base):
    __tablename__ = "party_slots"
    __table_args__ = (UniqueConstraint("slot_id", "position", name="uq_party_slot_position"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("save_slots.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    pokemon_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    pokemon_name_zh: Mapped[str] = mapped_column(String(120), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    hp_text: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    types: Mapped[list[str]] = mapped_column(JSONType, default=list)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StorageBoxEntry(Base):
    __tablename__ = "storage_box_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("save_slots.id"), nullable=False
    )
    box_code: Mapped[str] = mapped_column(String(20), nullable=False, default="BOX-1")
    pokemon_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    pokemon_name_zh: Mapped[str] = mapped_column(String(120), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    types: Mapped[list[str]] = mapped_column(JSONType, default=list)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("slot_id", "category", "item_name_zh", name="uq_inventory_item"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("save_slots.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    item_name_zh: Mapped[str] = mapped_column(String(120), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StoryProgressV2(Base):
    __tablename__ = "story_progress_v2"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("save_slots.id"), nullable=False, unique=True
    )
    act_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    chapter_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="推进主线")
    objective_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    turns_in_chapter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChapterState(Base):
    __tablename__ = "chapter_states"
    __table_args__ = (
        UniqueConstraint("slot_id", "chapter_index", name="uq_chapter_state_slot_chapter"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("save_slots.id"), nullable=False
    )
    chapter_index: Mapped[int] = mapped_column(Integer, nullable=False)
    act_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    core_conflict: Mapped[str | None] = mapped_column(Text, nullable=True)
    sacrifice_cost: Mapped[str | None] = mapped_column(Text, nullable=True)
    reward: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RomanceRoute(Base):
    __tablename__ = "romance_routes"
    __table_args__ = (UniqueConstraint("slot_id", "route_tag", name="uq_romance_route_slot_tag"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("save_slots.id"), nullable=False
    )
    route_tag: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    trait: Mapped[str | None] = mapped_column(Text, nullable=True)
    route_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    affection: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    route_state: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LegendaryState(Base):
    __tablename__ = "legendary_states"
    __table_args__ = (UniqueConstraint("slot_id", "slug_id", name="uq_legendary_state_slot_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("save_slots.id"), nullable=False
    )
    slug_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(120), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stance: Mapped[str | None] = mapped_column(String(40), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    seal_state: Mapped[str] = mapped_column(String(20), nullable=False, default="unstable")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorldMapV2(Base):
    __tablename__ = "world_maps_v2"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("save_slots.id"), nullable=False, unique=True
    )
    map_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=36)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    seed: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_node_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    visited_node_ids: Mapped[list[str]] = mapped_column(JSONType, default=list)
    biomes: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    chapter_route: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MapNodeV2(Base):
    __tablename__ = "map_nodes_v2"
    __table_args__ = (UniqueConstraint("world_map_id", "node_id", name="uq_world_map_node"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    world_map_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("world_maps_v2.id"), nullable=False
    )
    node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    x: Mapped[int] = mapped_column(Integer, nullable=False)
    y: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    gym_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(40), nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)


class MapEdgeV2(Base):
    __tablename__ = "map_edges_v2"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    world_map_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("world_maps_v2.id"), nullable=False
    )
    from_node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    to_node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    edge_type: Mapped[str] = mapped_column(String(20), nullable=False, default="road")
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)


class SessionTurnV2(Base):
    __tablename__ = "session_turns_v2"
    __table_args__ = (
        UniqueConstraint("slot_id", "turn_index", name="uq_session_turn_v2_slot_turn"),
        UniqueConstraint("slot_id", "client_turn_id", name="uq_session_turn_v2_slot_client_turn"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("save_slots.id"), nullable=False
    )
    source_turn_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("turns.id"), nullable=True
    )
    client_turn_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="done")
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    user_text: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_text: Mapped[str] = mapped_column(Text, nullable=False)
    planner_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    primary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrative_primary: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrative_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_options: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType, nullable=True)
    battle_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    state_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    provider_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_interactive_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_primary_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    done_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GameSlotLoreState(Base):
    __tablename__ = "game_slot_lore_state"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("save_slots.id"), nullable=False, unique=True
    )
    global_balance_index: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    human_power_dependency: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    cycle_instability: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    protocol_phase: Mapped[ProtocolPhase] = mapped_column(
        Enum(ProtocolPhase, name="protocol_phase"),
        nullable=False,
        default=ProtocolPhase.silent_sampling,
    )
    player_cross_signature_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    legendary_alignment: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GameSlotTimeState(Base):
    __tablename__ = "game_slot_time_state"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("save_slots.id"), nullable=False, unique=True
    )
    temporal_debt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    narrative_cohesion: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    judicative_stability: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    compilation_risk: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    phase3_stripping_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GameSlotFactionState(Base):
    __tablename__ = "game_slot_faction_state"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("save_slots.id"), nullable=False, unique=True
    )
    league_central_stability: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    league_public_faction_power: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    league_regional_defiance: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    white_ring_banist: Mapped[int] = mapped_column(Integer, nullable=False, default=35)
    white_ring_transitionist: Mapped[int] = mapped_column(Integer, nullable=False, default=45)
    white_ring_accelerationist: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    consortium_governance: Mapped[int] = mapped_column(Integer, nullable=False, default=45)
    consortium_expansion: Mapped[int] = mapped_column(Integer, nullable=False, default=35)
    consortium_substitution: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    grassroots_mutual_aid: Mapped[int] = mapped_column(Integer, nullable=False, default=45)
    grassroots_militia: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    grassroots_radicalisation: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    witnesses_intervention: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    witnesses_preservation: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    witnesses_resignation: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


Index("ix_turns_session", Turn.session_id)
Index("ix_turns_session_turn_index", Turn.session_id, Turn.turn_index)
Index("ix_sessions_user_deleted_updated", Session.user_id, Session.deleted, Session.updated_at)
Index("ix_sessions_world_seed", Session.world_seed)
Index("ix_timeline_session", TimelineEvent.session_id)
Index("ix_timeline_level", TimelineEvent.canon_level)
Index("ix_timeline_time_class", TimelineEvent.time_class)
Index("ix_timeline_session_created", TimelineEvent.session_id, TimelineEvent.created_at)
Index("ix_chunks_session", MemoryChunk.session_id)
Index("ix_chunks_time_class", MemoryChunk.time_class)
Index("ix_threads_session_status", OpenThread.session_id, OpenThread.status)
Index("ix_audit_session_action", AuditLog.session_id, AuditLog.action)
Index("ix_canon_pokemon_slug", CanonPokemon.slug_id)
Index("ix_canon_moves_slug", CanonMove.slug_id)
Index("ix_save_slots_user_updated", SaveSlot.user_id, SaveSlot.updated_at)
Index("ix_party_slots_slot_position", PartySlot.slot_id, PartySlot.position)
Index("ix_storage_box_slot", StorageBoxEntry.slot_id)
Index("ix_inventory_slot_category", InventoryItem.slot_id, InventoryItem.category)
Index("ix_story_progress_slot", StoryProgressV2.slot_id)
Index("ix_chapter_states_slot", ChapterState.slot_id)
Index("ix_romance_routes_slot", RomanceRoute.slot_id)
Index("ix_legendary_states_slot", LegendaryState.slot_id)
Index("ix_world_maps_slot", WorldMapV2.slot_id)
Index("ix_map_nodes_world_map", MapNodeV2.world_map_id)
Index("ix_map_edges_world_map", MapEdgeV2.world_map_id)
Index("ix_session_turns_v2_slot", SessionTurnV2.slot_id)
Index("ix_slot_lore_state_slot", GameSlotLoreState.slot_id)
Index("ix_slot_time_state_slot", GameSlotTimeState.slot_id)
Index("ix_slot_faction_state_slot", GameSlotFactionState.slot_id)
