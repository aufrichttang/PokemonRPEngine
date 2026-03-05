from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import (
    GameSlotFactionState,
    GameSlotLoreState,
    GameSlotTimeState,
    InventoryItem,
    PartySlot,
    PlayerProfileV2,
    SaveSlot,
    SessionTurnV2,
    StorageBoxEntry,
    StoryProgressV2,
    Turn,
    User,
)
from app.db.models import (
    Session as StorySession,
)
from app.kernels.event_classifier import classify_event_metadata
from app.services.chat_service import ChatService
from app.services.session_service import SessionService
from app.services.v2.kernel_summary_service import KernelSummaryService
from app.services.v2.state_reducer import SlotSnapshot, StateReducer
from app.services.v2.turn_pipeline import TurnPipelineService


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _public_world_profile(value: Any) -> dict[str, Any]:
    profile = dict(value) if isinstance(value, dict) else {}
    profile.pop("map_data", None)
    return profile


class GameFacadeService:
    def __init__(
        self,
        *,
        session_service: SessionService,
        chat_service: ChatService,
        state_reducer: StateReducer | None = None,
        turn_pipeline: TurnPipelineService | None = None,
    ) -> None:
        self.session_service = session_service
        self.chat_service = chat_service
        self.state_reducer = state_reducer or StateReducer()
        self.kernel_summary_service = KernelSummaryService()
        self.turn_pipeline = turn_pipeline or TurnPipelineService(
            chat_service=self.chat_service,
            state_reducer=self.state_reducer,
        )

    def create_slot(
        self,
        db: Session,
        *,
        current_user: User,
        slot_name: str,
        world_seed: str | None,
        canon_gen: int,
        canon_game: str | None,
        player_profile: dict[str, Any] | None,
    ) -> dict[str, Any]:
        session_obj = self.session_service.create_session(
            db,
            user_id=current_user.id,
            title=slot_name,
            world_template_id=None,
            world_seed=world_seed,
            canon_gen=canon_gen,
            canon_game=canon_game,
            custom_lore_enabled=False,
            player_profile=player_profile,
            ensure_v3_slot=False,
        )
        slot = db.execute(
            select(SaveSlot).where(SaveSlot.session_id == session_obj.id)
        ).scalar_one_or_none()
        if slot is None:
            slot = SaveSlot(
                user_id=current_user.id,
                session_id=session_obj.id,
                slot_name=slot_name,
                schema_version=3,
                world_seed=session_obj.world_seed,
                is_active=True,
            )
            db.add(slot)
            db.flush()
        elif int(slot.schema_version or 0) < 3:
            slot.schema_version = 3
            db.add(slot)
            db.flush()

        snapshot = self.state_reducer.sync_slot_from_session(db, slot=slot, session_obj=session_obj)
        self._sync_turn_rows(db, slot=slot, session_obj=session_obj, snapshot=snapshot)
        db.commit()
        db.refresh(slot)
        return self.get_slot(db, slot_id=slot.id, current_user=current_user)

    def list_slots(
        self, db: Session, *, current_user: User, page: int, size: int
    ) -> dict[str, Any]:
        rows = (
            db.execute(
                select(SaveSlot)
                .where(SaveSlot.user_id == current_user.id, SaveSlot.is_active.is_(True))
                .order_by(SaveSlot.updated_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
            .scalars()
            .all()
        )
        return {
            "items": [
                {
                    "slot_id": str(row.id),
                    "slot_name": row.slot_name,
                    "session_id": str(row.session_id),
                    "world_seed": row.world_seed,
                    "schema_version": row.schema_version,
                    "updated_at": row.updated_at,
                }
                for row in rows
            ]
        }

    def get_slot(self, db: Session, *, slot_id: uuid.UUID, current_user: User) -> dict[str, Any]:
        slot = self._get_slot_or_raise(db, slot_id=slot_id, current_user=current_user)
        session_obj = self._get_session_or_raise(db, session_id=slot.session_id)
        # Read path should stay read-only. Writing here can create lock contention
        # with turn creation on SQLite.
        return self._serialize_slot(db, slot=slot, session_obj=session_obj)

    def get_lore(self, db: Session, *, slot_id: uuid.UUID, current_user: User) -> dict[str, Any]:
        slot = self._get_slot_or_raise(db, slot_id=slot_id, current_user=current_user)
        lore_row, _, _ = self.kernel_summary_service.get_rows(db, slot_id=slot.id)
        return {
            "slot_id": str(slot.id),
            "lore_kernel": self.kernel_summary_service.summarize_lore(lore_row),
        }

    def get_time(self, db: Session, *, slot_id: uuid.UUID, current_user: User) -> dict[str, Any]:
        slot = self._get_slot_or_raise(db, slot_id=slot_id, current_user=current_user)
        _, time_row, _ = self.kernel_summary_service.get_rows(db, slot_id=slot.id)
        return {
            "slot_id": str(slot.id),
            "time_kernel": self.kernel_summary_service.summarize_time(time_row),
        }

    def get_factions(
        self, db: Session, *, slot_id: uuid.UUID, current_user: User
    ) -> dict[str, Any]:
        slot = self._get_slot_or_raise(db, slot_id=slot_id, current_user=current_user)
        _, _, faction_row = self.kernel_summary_service.get_rows(db, slot_id=slot.id)
        return {
            "slot_id": str(slot.id),
            "faction_kernel": self.kernel_summary_service.summarize_faction(faction_row),
        }

    def reclassify_memories(
        self, db: Session, *, slot_id: uuid.UUID, current_user: User
    ) -> dict[str, Any]:
        slot = self._get_slot_or_raise(db, slot_id=slot_id, current_user=current_user)
        if current_user.role.value not in {"admin", "operator"}:
            raise AppError(code="forbidden", message="No debug permission", status_code=403)
        session_obj = self._get_session_or_raise(db, session_id=slot.session_id)
        from app.db.models import MemoryChunk, TimelineEvent

        events = (
            db.query(TimelineEvent)
            .filter(TimelineEvent.session_id == session_obj.id)
            .order_by(TimelineEvent.created_at.desc())
            .all()
        )
        chunks = (
            db.query(MemoryChunk)
            .filter(MemoryChunk.session_id == session_obj.id)
            .order_by(MemoryChunk.created_at.desc())
            .all()
        )
        touched = {"events": 0, "chunks": 0}
        for row in events:
            meta = classify_event_metadata(
                text=row.event_text,
                canon_level=row.canon_level.value,
                actors=row.actors,
            )
            row.time_class = meta["time_class"]
            row.source_trust = meta["source_trust"]
            row.witness_count = meta["witness_count"]
            row.narrative_conflict_score = meta["narrative_conflict_score"]
            row.canon_legacy_tags = meta["canon_legacy_tags"]
            db.add(row)
            touched["events"] += 1
        for row in chunks:
            meta = classify_event_metadata(
                text=row.chunk_text,
                canon_level="implied",
                actors=(row.tags or {}).get("actors", []),
            )
            row.time_class = meta["time_class"]
            row.source_trust = meta["source_trust"]
            row.witness_count = meta["witness_count"]
            row.narrative_conflict_score = meta["narrative_conflict_score"]
            row.canon_legacy_tags = meta["canon_legacy_tags"]
            db.add(row)
            touched["chunks"] += 1
        db.commit()
        return {"slot_id": str(slot.id), "reclassified": touched}

    async def turn(
        self,
        db: Session,
        *,
        slot_id: uuid.UUID,
        current_user: User,
        text: str,
        language: str,
        pace: str = "balanced",
        client_turn_id: str | None = None,
    ) -> dict[str, Any]:
        slot = self._get_slot_or_raise(db, slot_id=slot_id, current_user=current_user)
        session_obj = self._get_session_or_raise(db, session_id=slot.session_id)
        return await self.turn_pipeline.run_non_stream(
            db,
            slot=slot,
            session_obj=session_obj,
            user_text=text,
            language=language,
            pace=pace,
            client_turn_id=client_turn_id,
        )

    async def turn_stream(
        self,
        db: Session,
        *,
        slot_id: uuid.UUID,
        current_user: User,
        text: str,
        language: str,
        pace: str = "balanced",
        client_turn_id: str | None = None,
    ) -> AsyncIterator[str]:
        slot = self._get_slot_or_raise(db, slot_id=slot_id, current_user=current_user)
        session_obj = self._get_session_or_raise(db, session_id=slot.session_id)
        async for event in self.turn_pipeline.run_stream(
            db,
            slot=slot,
            session_obj=session_obj,
            user_text=text,
            language=language,
            pace=pace,
            client_turn_id=client_turn_id,
        ):
            yield event

    async def execute_action(
        self,
        db: Session,
        *,
        slot_id: uuid.UUID,
        current_user: User,
        action_id: str,
        stream: bool,
        language: str,
        pace: str = "balanced",
        client_turn_id: str | None = None,
    ) -> dict[str, Any] | AsyncIterator[str]:
        slot = self._get_slot_or_raise(db, slot_id=slot_id, current_user=current_user)
        latest_turn = (
            db.execute(
                select(SessionTurnV2)
                .where(
                    SessionTurnV2.slot_id == slot.id,
                    SessionTurnV2.status == "done",
                )
                .order_by(SessionTurnV2.turn_index.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if latest_turn is None:
            raise AppError(
                code="action_source_missing", message="No turn available", status_code=400
            )
        options = latest_turn.action_options or []
        chosen = next((o for o in options if str(o.get("id")) == action_id), None)
        if not isinstance(chosen, dict):
            raise AppError(
                code="action_not_found", message="Action option not found", status_code=404
            )
        send_text = str(chosen.get("send_text") or chosen.get("text") or "").strip()
        if not send_text:
            raise AppError(
                code="action_text_empty", message="Action option is empty", status_code=400
            )
        if stream:
            return self.turn_stream(
                db,
                slot_id=slot_id,
                current_user=current_user,
                text=send_text,
                language=language,
                pace=pace,
                client_turn_id=client_turn_id,
            )
        return await self.turn(
            db,
            slot_id=slot_id,
            current_user=current_user,
            text=send_text,
            language=language,
            pace=pace,
            client_turn_id=client_turn_id,
        )

    def _sync_turn_rows(
        self,
        db: Session,
        *,
        slot: SaveSlot,
        session_obj: StorySession,
        snapshot: SlotSnapshot,
    ) -> None:
        source_turns = (
            db.execute(
                select(Turn)
                .where(Turn.session_id == session_obj.id)
                .order_by(Turn.turn_index.asc())
            )
            .scalars()
            .all()
        )
        for turn in source_turns:
            narrative_primary = turn.assistant_text
            narrative_detail = None
            if isinstance(turn.assistant_text, str) and "<!--JSON-->" in turn.assistant_text:
                narrative_primary = turn.assistant_text.split("<!--JSON-->")[0].strip()
                narrative_detail = turn.assistant_text
            self.state_reducer.upsert_turn_v2(
                db,
                slot=slot,
                turn=turn,
                narrative_primary=narrative_primary,
                narrative_detail=narrative_detail,
                state_snapshot=self._snapshot_payload(snapshot),
            )

    def _serialize_slot(
        self, db: Session, *, slot: SaveSlot, session_obj: StorySession
    ) -> dict[str, Any]:
        profile = db.execute(
            select(PlayerProfileV2).where(PlayerProfileV2.slot_id == slot.id)
        ).scalar_one_or_none()
        story = db.execute(
            select(StoryProgressV2).where(StoryProgressV2.slot_id == slot.id)
        ).scalar_one_or_none()
        party = (
            db.execute(
                select(PartySlot)
                .where(PartySlot.slot_id == slot.id)
                .order_by(PartySlot.position.asc())
            )
            .scalars()
            .all()
        )
        storage = (
            db.execute(select(StorageBoxEntry).where(StorageBoxEntry.slot_id == slot.id))
            .scalars()
            .all()
        )
        inventory = (
            db.execute(select(InventoryItem).where(InventoryItem.slot_id == slot.id))
            .scalars()
            .all()
        )
        turns = list(
            db.execute(
                select(SessionTurnV2)
                .where(SessionTurnV2.slot_id == slot.id)
                .order_by(SessionTurnV2.turn_index.desc())
                .limit(50)
            )
            .scalars()
            .all()
        )
        turns.reverse()

        inventory_grouped: dict[str, list[dict[str, Any]]] = {}
        for item in inventory:
            inventory_grouped.setdefault(item.category, []).append(
                {"name_zh": item.item_name_zh, "count": item.count, "meta": item.meta or {}}
            )

        lore_row = db.execute(
            select(GameSlotLoreState).where(GameSlotLoreState.slot_id == slot.id)
        ).scalar_one_or_none()
        time_row = db.execute(
            select(GameSlotTimeState).where(GameSlotTimeState.slot_id == slot.id)
        ).scalar_one_or_none()
        faction_row = db.execute(
            select(GameSlotFactionState).where(GameSlotFactionState.slot_id == slot.id)
        ).scalar_one_or_none()

        return {
            "slot_id": str(slot.id),
            "slot_name": slot.slot_name,
            "schema_version": slot.schema_version,
            "session_id": str(slot.session_id),
            "world_seed": slot.world_seed,
            "world_profile": _public_world_profile(session_obj.world_profile),
            "player_profile": {
                "name": profile.name if profile else "",
                "gender": profile.gender if profile else "",
                "age": profile.age if profile else 18,
                "height_cm": profile.height_cm if profile else 170,
                "appearance": profile.appearance if profile else "",
                "personality": profile.personality if profile else "",
                "background": profile.background if profile else "",
                "detail": profile.detail if profile else "",
                "backstory": profile.backstory if profile else {},
            },
            "story_progress": {
                "act": story.act_index if story else 1,
                "chapter": story.chapter_index if story else 1,
                "objective": story.objective if story else "推进主线",
                "objective_status": story.objective_status if story else "pending",
                "turns_in_chapter": story.turns_in_chapter if story else 0,
                "risk_level": story.risk_level if story else "medium",
            },
            "party": [
                {
                    "position": p.position,
                    "slug_id": p.pokemon_slug,
                    "name_zh": p.pokemon_name_zh,
                    "level": p.level,
                    "hp": p.hp_text,
                    "status": p.status_text,
                    "types": p.types or [],
                }
                for p in party
            ],
            "storage_box": [
                {
                    "slug_id": s.pokemon_slug,
                    "name_zh": s.pokemon_name_zh,
                    "level": s.level,
                    "types": s.types or [],
                }
                for s in storage
            ],
            "inventory": inventory_grouped,
            "turns": [
                {
                    "turn_id": str(t.id),
                    "turn_index": t.turn_index,
                    "user_text": t.user_text,
                    "assistant_text": t.assistant_text,
                    "narrative": {
                        "primary": t.narrative_primary or t.assistant_text,
                        "detail": t.narrative_detail,
                    },
                    "action_options": t.action_options or [],
                    "battle_summary": t.battle_summary or {},
                    "state_snapshot": t.state_snapshot or {},
                    "status": t.status,
                    "timings": {
                        "first_interactive_ms": t.first_interactive_ms,
                        "first_primary_ms": t.first_primary_ms,
                        "done_ms": t.done_ms,
                    },
                    "created_at": t.created_at,
                }
                for t in turns
            ],
            "lore_kernel_summary": self.kernel_summary_service.summarize_lore(lore_row),
            "time_kernel_summary": self.kernel_summary_service.summarize_time(time_row),
            "faction_kernel_summary": self.kernel_summary_service.summarize_faction(faction_row),
            "active_warnings": self.kernel_summary_service.warnings(lore=lore_row, time=time_row),
        }

    def _snapshot_payload(self, snapshot: SlotSnapshot) -> dict[str, Any]:
        return {
            "slot_id": str(snapshot.slot_id),
            "session_id": str(snapshot.session_id),
            "turn_index": snapshot.turn_index,
            "story_progress": snapshot.story_progress,
            "location": snapshot.player_state.get("location"),
            "money": snapshot.player_state.get("money"),
            "badges": snapshot.player_state.get("badges", []),
        }

    def _get_slot_or_raise(
        self, db: Session, *, slot_id: uuid.UUID, current_user: User
    ) -> SaveSlot:
        row = db.execute(
            select(SaveSlot).where(SaveSlot.id == slot_id, SaveSlot.is_active.is_(True))
        ).scalar_one_or_none()
        if row is None:
            raise AppError(code="slot_not_found", message="Save slot not found", status_code=404)
        if row.user_id != current_user.id and current_user.role.value not in {"admin", "operator"}:
            raise AppError(code="forbidden", message="No access to slot", status_code=403)
        if int(row.schema_version or 0) < 3:
            raise AppError(
                code="slot_upgrade_required",
                message="This save slot is from old schema. Please create a new V3 slot.",
                status_code=409,
            )
        return row

    def _get_session_or_raise(self, db: Session, *, session_id: uuid.UUID) -> StorySession:
        session_obj = db.execute(
            select(StorySession).where(
                StorySession.id == session_id, StorySession.deleted.is_(False)
            )
        ).scalar_one_or_none()
        if session_obj is None:
            raise AppError(code="session_not_found", message="Session not found", status_code=404)
        return session_obj

    def dump_slot(self, db: Session, *, slot_id: uuid.UUID, current_user: User) -> str:
        payload = self.get_slot(db, slot_id=slot_id, current_user=current_user)
        return json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default)
