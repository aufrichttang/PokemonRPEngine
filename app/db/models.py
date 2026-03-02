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
    canon_gen: Mapped[int] = mapped_column(Integer, default=9, nullable=False)
    canon_game: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custom_lore_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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


Index("ix_turns_session", Turn.session_id)
Index("ix_turns_session_turn_index", Turn.session_id, Turn.turn_index)
Index("ix_sessions_user_deleted_updated", Session.user_id, Session.deleted, Session.updated_at)
Index("ix_timeline_session", TimelineEvent.session_id)
Index("ix_timeline_level", TimelineEvent.canon_level)
Index("ix_timeline_session_created", TimelineEvent.session_id, TimelineEvent.created_at)
Index("ix_chunks_session", MemoryChunk.session_id)
Index("ix_threads_session_status", OpenThread.session_id, OpenThread.status)
Index("ix_audit_session_action", AuditLog.session_id, AuditLog.action)
Index("ix_canon_pokemon_slug", CanonPokemon.slug_id)
Index("ix_canon_moves_slug", CanonMove.slug_id)
