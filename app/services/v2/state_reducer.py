from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    ChapterState,
    GameSlotFactionState,
    GameSlotLoreState,
    GameSlotTimeState,
    InventoryItem,
    LegendaryState,
    PartySlot,
    PlayerProfileV2,
    RomanceRoute,
    SaveSlot,
    SessionTurnV2,
    StorageBoxEntry,
    StoryProgressV2,
    Turn,
)
from app.db.models import (
    Session as StorySession,
)
from app.services.v2.story_state_engine import StoryStateEngine


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


@dataclass
class SlotSnapshot:
    slot_id: uuid.UUID
    session_id: uuid.UUID
    turn_index: int
    world_profile: dict[str, Any]
    player_profile: dict[str, Any]
    player_state: dict[str, Any]
    story_progress: dict[str, Any]


class StateReducer:
    INVENTORY_CATEGORIES = {
        "balls",
        "medicine",
        "battle_items",
        "berries",
        "key_items",
        "materials",
        "misc",
    }

    def __init__(self, story_state_engine: StoryStateEngine | None = None) -> None:
        self.story_state_engine = story_state_engine or StoryStateEngine()

    def build_snapshot(
        self, *, slot: SaveSlot, session_obj: StorySession, turn_index: int
    ) -> SlotSnapshot:
        world_profile = _as_dict(session_obj.world_profile)
        player_profile = _as_dict(session_obj.player_profile)
        player_state = _as_dict(session_obj.player_state)
        story_progress = _as_dict(player_state.get("story_progress"))
        return SlotSnapshot(
            slot_id=slot.id,
            session_id=session_obj.id,
            turn_index=turn_index,
            world_profile=world_profile,
            player_profile=player_profile,
            player_state=player_state,
            story_progress=story_progress,
        )

    def sync_slot_from_session(
        self, db: Session, *, slot: SaveSlot, session_obj: StorySession
    ) -> SlotSnapshot:
        latest_turn = db.execute(
            select(Turn)
            .where(Turn.session_id == session_obj.id)
            .order_by(Turn.turn_index.desc())
            .limit(1)
        ).scalar_one_or_none()
        turn_index = latest_turn.turn_index if latest_turn else 1
        snapshot = self.build_snapshot(slot=slot, session_obj=session_obj, turn_index=turn_index)
        self._sync_profile(db, snapshot=snapshot)
        self._sync_party_and_box(db, snapshot=snapshot)
        self._sync_inventory(db, snapshot=snapshot)
        self._sync_story(db, snapshot=snapshot)
        self._sync_romance(db, snapshot=snapshot)
        self._sync_legendary(db, snapshot=snapshot)
        self._sync_kernel_rows(db, snapshot=snapshot)
        return snapshot

    def upsert_turn_v2(
        self,
        db: Session,
        *,
        slot: SaveSlot,
        turn: Turn,
        narrative_primary: str,
        narrative_detail: str | None,
        state_snapshot: dict[str, Any],
        client_turn_id: str | None = None,
        status: str = "done",
        planner_payload: dict[str, Any] | None = None,
        first_interactive_ms: int | None = None,
        first_primary_ms: int | None = None,
        done_ms: int | None = None,
    ) -> SessionTurnV2:
        row = db.execute(
            select(SessionTurnV2).where(
                SessionTurnV2.slot_id == slot.id,
                SessionTurnV2.turn_index == turn.turn_index,
            )
        ).scalar_one_or_none()
        if row is None:
            row = SessionTurnV2(
                slot_id=slot.id,
                source_turn_id=turn.id,
                client_turn_id=client_turn_id,
                status=status,
                turn_index=turn.turn_index,
                user_text=turn.user_text,
                assistant_text=turn.assistant_text,
                planner_payload=planner_payload,
                primary_text=narrative_primary,
                detail_text=narrative_detail,
                narrative_primary=narrative_primary,
                narrative_detail=narrative_detail,
                action_options=turn.action_options or [],
                battle_summary=turn.battle_summary or {},
                state_snapshot=state_snapshot,
                provider_latency_ms=turn.provider_latency_ms,
                first_interactive_ms=first_interactive_ms,
                first_primary_ms=first_primary_ms,
                done_ms=done_ms,
                token_usage=turn.token_usage or {},
            )
            db.add(row)
        else:
            row.source_turn_id = turn.id
            row.client_turn_id = client_turn_id or row.client_turn_id
            row.status = status
            row.user_text = turn.user_text
            row.assistant_text = turn.assistant_text
            row.planner_payload = (
                planner_payload if planner_payload is not None else row.planner_payload
            )
            row.primary_text = narrative_primary
            row.detail_text = narrative_detail
            row.narrative_primary = narrative_primary
            row.narrative_detail = narrative_detail
            row.action_options = turn.action_options or []
            row.battle_summary = turn.battle_summary or {}
            row.state_snapshot = state_snapshot
            row.provider_latency_ms = turn.provider_latency_ms
            if first_interactive_ms is not None:
                row.first_interactive_ms = first_interactive_ms
            if first_primary_ms is not None:
                row.first_primary_ms = first_primary_ms
            if done_ms is not None:
                row.done_ms = done_ms
            row.token_usage = turn.token_usage or {}
            db.add(row)
        return row

    def _sync_profile(self, db: Session, *, snapshot: SlotSnapshot) -> None:
        profile = snapshot.player_profile
        row = db.execute(
            select(PlayerProfileV2).where(PlayerProfileV2.slot_id == snapshot.slot_id)
        ).scalar_one_or_none()
        if row is None:
            row = PlayerProfileV2(
                slot_id=snapshot.slot_id,
                name=str(profile.get("name") or "主角"),
                gender=str(profile.get("gender") or "未设定"),
                age=int(profile.get("age") or 18),
                height_cm=int(profile.get("height_cm") or 170),
            )
        row.name = str(profile.get("name") or row.name)
        row.gender = str(profile.get("gender") or row.gender)
        row.age = int(profile.get("age") or row.age or 18)
        row.height_cm = int(profile.get("height_cm") or row.height_cm or 170)
        row.appearance = str(profile.get("appearance") or "") or None
        row.personality = str(profile.get("personality") or "") or None
        row.background = str(profile.get("background") or "") or None
        row.detail = str(profile.get("detail") or "") or None
        row.backstory = _as_dict(profile.get("backstory"))
        db.add(row)

    def _sync_party_and_box(self, db: Session, *, snapshot: SlotSnapshot) -> None:
        db.execute(delete(PartySlot).where(PartySlot.slot_id == snapshot.slot_id))
        db.execute(delete(StorageBoxEntry).where(StorageBoxEntry.slot_id == snapshot.slot_id))

        team = _as_list(snapshot.player_state.get("team"))
        box = _as_list(snapshot.player_state.get("storage_box"))

        for idx, item in enumerate(team[:6], start=1):
            entry = self._pokemon_entry(item)
            if not entry:
                continue
            db.add(
                PartySlot(
                    slot_id=snapshot.slot_id,
                    position=idx,
                    pokemon_slug=entry["slug"],
                    pokemon_name_zh=entry["name"],
                    level=entry["level"],
                    hp_text=entry.get("hp"),
                    status_text=entry.get("status"),
                    types=entry.get("types", []),
                    meta=entry.get("meta"),
                )
            )

        for item in team[6:]:
            box.append(item)

        for item in box:
            entry = self._pokemon_entry(item)
            if not entry:
                continue
            db.add(
                StorageBoxEntry(
                    slot_id=snapshot.slot_id,
                    box_code="BOX-1",
                    pokemon_slug=entry["slug"],
                    pokemon_name_zh=entry["name"],
                    level=entry["level"],
                    types=entry.get("types", []),
                    meta=entry.get("meta"),
                )
            )

    def _sync_inventory(self, db: Session, *, snapshot: SlotSnapshot) -> None:
        db.execute(delete(InventoryItem).where(InventoryItem.slot_id == snapshot.slot_id))
        inventory = _as_dict(snapshot.player_state.get("inventory"))
        for category, values in inventory.items():
            safe_category = category if category in self.INVENTORY_CATEGORIES else "misc"
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, str) and item.strip():
                        db.add(
                            InventoryItem(
                                slot_id=snapshot.slot_id,
                                category=safe_category,
                                item_name_zh=item.strip(),
                                count=1,
                            )
                        )
                    elif isinstance(item, dict):
                        name = str(item.get("name_zh") or item.get("name") or "").strip()
                        if not name:
                            continue
                        count = int(item.get("count") or 1)
                        db.add(
                            InventoryItem(
                                slot_id=snapshot.slot_id,
                                category=safe_category,
                                item_name_zh=name,
                                count=max(1, count),
                                meta=item,
                            )
                        )
            elif isinstance(values, dict):
                for k, v in values.items():
                    name = str(k).strip()
                    if not name:
                        continue
                    count = int(v) if isinstance(v, int) else 1
                    db.add(
                        InventoryItem(
                            slot_id=snapshot.slot_id,
                            category=safe_category,
                            item_name_zh=name,
                            count=max(1, count),
                        )
                    )

    def _sync_story(self, db: Session, *, snapshot: SlotSnapshot) -> None:
        progress = snapshot.story_progress
        row = db.execute(
            select(StoryProgressV2).where(StoryProgressV2.slot_id == snapshot.slot_id)
        ).scalar_one_or_none()
        if row is None:
            row = StoryProgressV2(slot_id=snapshot.slot_id)
        row.act_index = int(progress.get("act") or 1)
        row.chapter_index = int(progress.get("chapter") or 1)
        row.objective = str(progress.get("objective") or "推进主线")
        row.objective_status = str(progress.get("objective_status") or "pending")
        row.turns_in_chapter = int(progress.get("turns_in_chapter") or 0)
        row.risk_level = self._risk_level(row.chapter_index)
        db.add(row)

        db.execute(delete(ChapterState).where(ChapterState.slot_id == snapshot.slot_id))
        story_blueprint = _as_dict(snapshot.world_profile.get("story_blueprint"))
        for act in _as_list(story_blueprint.get("acts")):
            if not isinstance(act, dict):
                continue
            act_index = int(act.get("act_index") or 1)
            for chapter in _as_list(act.get("chapters")):
                if not isinstance(chapter, dict):
                    continue
                db.add(
                    ChapterState(
                        slot_id=snapshot.slot_id,
                        chapter_index=int(chapter.get("chapter_index") or 1),
                        act_index=act_index,
                        title=str(chapter.get("title") or "章节"),
                        objective=str(chapter.get("objective") or "推进主线"),
                        status=str(chapter.get("status") or "pending"),
                        core_conflict=str(chapter.get("core_conflict") or "") or None,
                        sacrifice_cost=str(chapter.get("sacrifice_cost") or "") or None,
                        reward=str(chapter.get("reward") or "") or None,
                    )
                )


    def _sync_romance(self, db: Session, *, snapshot: SlotSnapshot) -> None:
        db.execute(delete(RomanceRoute).where(RomanceRoute.slot_id == snapshot.slot_id))
        for cand in _as_list(snapshot.world_profile.get("romance_candidates")):
            if not isinstance(cand, dict):
                continue
            route_tag = str(cand.get("route_tag") or "").strip()
            name = str(cand.get("name") or "").strip()
            role = str(cand.get("role") or "").strip()
            if not route_tag or not name:
                continue
            db.add(
                RomanceRoute(
                    slot_id=snapshot.slot_id,
                    route_tag=route_tag,
                    name=name,
                    role=role or "关键角色",
                    trait=str(cand.get("trait") or "") or None,
                    route_hint=str(cand.get("route_hint") or "") or None,
                    affection=0,
                    route_state="open",
                )
            )

    def _sync_legendary(self, db: Session, *, snapshot: SlotSnapshot) -> None:
        db.execute(delete(LegendaryState).where(LegendaryState.slot_id == snapshot.slot_id))
        legendary_web = _as_dict(snapshot.world_profile.get("legendary_web"))
        for node in _as_list(legendary_web.get("nodes")):
            if not isinstance(node, dict):
                continue
            slug_id = str(node.get("slug_id") or "").strip()
            name_zh = str(node.get("name_zh") or "").strip()
            if not slug_id or not name_zh:
                continue
            db.add(
                LegendaryState(
                    slot_id=snapshot.slot_id,
                    slug_id=slug_id,
                    name_zh=name_zh,
                    domain=str(node.get("domain") or "") or None,
                    stance=str(node.get("stance") or "") or None,
                    risk_level=str(node.get("risk_level") or "") or None,
                    seal_state="unstable",
                )
            )

    def _pokemon_entry(self, item: Any) -> dict[str, Any] | None:
        if isinstance(item, str):
            name = item.strip()
            if not name:
                return None
            return {"slug": name.lower().replace(" ", "-"), "name": name, "level": 5}
        if not isinstance(item, dict):
            return None
        slug = str(item.get("slug_id") or item.get("id") or "").strip()
        name = str(item.get("name_zh") or item.get("name") or item.get("species") or "").strip()
        if not slug and not name:
            return None
        return {
            "slug": slug or name.lower().replace(" ", "-"),
            "name": name or slug,
            "level": int(item.get("level") or 5),
            "hp": str(item.get("hp") or "") or None,
            "status": str(item.get("status") or item.get("condition") or "") or None,
            "types": _as_list(item.get("types")),
            "meta": item,
        }

    def _risk_level(self, chapter_idx: int) -> str:
        if chapter_idx <= 2:
            return "medium"
        if chapter_idx <= 5:
            return "high"
        return "extreme"

    def _sync_kernel_rows(self, db: Session, *, snapshot: SlotSnapshot) -> None:
        slot = db.execute(
            select(SaveSlot).where(SaveSlot.id == snapshot.slot_id)
        ).scalar_one_or_none()
        if slot is None:
            return
        lore = db.execute(
            select(GameSlotLoreState).where(GameSlotLoreState.slot_id == slot.id)
        ).scalar_one_or_none()
        time_state = db.execute(
            select(GameSlotTimeState).where(GameSlotTimeState.slot_id == slot.id)
        ).scalar_one_or_none()
        faction = db.execute(
            select(GameSlotFactionState).where(GameSlotFactionState.slot_id == slot.id)
        ).scalar_one_or_none()
        if lore is None or time_state is None or faction is None:
            self.story_state_engine.ensure_kernel_rows(db, slot_id=slot.id)
