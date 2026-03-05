from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    GameSlotFactionState,
    GameSlotLoreState,
    GameSlotTimeState,
    ProtocolPhase,
    SaveSlot,
)
from app.db.models import Session as StorySession
from app.kernels.event_classifier import clamp_0_100
from app.kernels.rules import faction_rules, lore_rules


@dataclass
class KernelApplyResult:
    slot_id: uuid.UUID
    lore_delta: dict[str, int]
    time_delta: dict[str, int]
    faction_delta: dict[str, int]
    active_warnings: list[str]


class StoryStateEngine:
    def ensure_slot_for_session(self, db: Session, *, session_obj: StorySession) -> SaveSlot:
        slot = db.execute(
            select(SaveSlot).where(SaveSlot.session_id == session_obj.id)
        ).scalar_one_or_none()
        if slot is None:
            slot = SaveSlot(
                user_id=session_obj.user_id,
                session_id=session_obj.id,
                slot_name=session_obj.title or "新冒险",
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
        return slot

    def ensure_kernel_rows(
        self,
        db: Session,
        *,
        slot_id: uuid.UUID,
    ) -> tuple[GameSlotLoreState, GameSlotTimeState, GameSlotFactionState]:
        lore_row = db.execute(
            select(GameSlotLoreState).where(GameSlotLoreState.slot_id == slot_id)
        ).scalar_one_or_none()
        if lore_row is None:
            defaults = lore_rules().get("defaults", {})
            lore_row = GameSlotLoreState(
                slot_id=slot_id,
                global_balance_index=int(defaults.get("global_balance_index", 50)),
                human_power_dependency=int(defaults.get("human_power_dependency", 50)),
                cycle_instability=int(defaults.get("cycle_instability", 20)),
                protocol_phase=ProtocolPhase.silent_sampling,
                player_cross_signature_level=int(defaults.get("player_cross_signature_level", 0)),
                legendary_alignment={
                    "dialga": 0,
                    "palkia": 0,
                    "giratina": 0,
                    "lake_trio": 0,
                },
            )
            db.add(lore_row)
            db.flush()

        time_row = db.execute(
            select(GameSlotTimeState).where(GameSlotTimeState.slot_id == slot_id)
        ).scalar_one_or_none()
        if time_row is None:
            time_row = GameSlotTimeState(slot_id=slot_id)
            db.add(time_row)
            db.flush()

        faction_row = db.execute(
            select(GameSlotFactionState).where(GameSlotFactionState.slot_id == slot_id)
        ).scalar_one_or_none()
        if faction_row is None:
            faction_row = GameSlotFactionState(slot_id=slot_id)
            db.add(faction_row)
            db.flush()

        return lore_row, time_row, faction_row

    def _phase_for_instability(self, instability: int) -> ProtocolPhase:
        thresholds = lore_rules().get("protocol_phase_thresholds", [])
        normalized = clamp_0_100(instability)
        for item in thresholds:
            if normalized <= int(item.get("max_cycle_instability", 100)):
                name = str(item.get("phase", ProtocolPhase.silent_sampling.value))
                return ProtocolPhase(name)
        return ProtocolPhase.silent_sampling

    def _apply_lore_delta(
        self,
        *,
        lore_row: GameSlotLoreState,
        text: str,
        battle_summary: dict[str, Any] | None,
    ) -> dict[str, int]:
        delta = {
            "global_balance_index": 0,
            "human_power_dependency": 0,
            "cycle_instability": 0,
            "player_cross_signature_level": 0,
        }
        lowered = text.lower()
        if any(k in lowered for k in ("神兽", "封印", "权柄", "裁定", "阿尔宙斯")):
            delta["cycle_instability"] += 4
            delta["player_cross_signature_level"] += 1
        if any(k in lowered for k in ("联盟", "道馆", "秩序")):
            delta["global_balance_index"] += 2
            delta["human_power_dependency"] += 1
        if any(k in lowered for k in ("失控", "崩裂", "暴走", "牺牲")):
            delta["cycle_instability"] += 3
            delta["global_balance_index"] -= 2
        if battle_summary:
            delta["cycle_instability"] += 2
            delta["human_power_dependency"] += 1

        lore_row.global_balance_index = clamp_0_100(
            lore_row.global_balance_index + delta["global_balance_index"]
        )
        lore_row.human_power_dependency = clamp_0_100(
            lore_row.human_power_dependency + delta["human_power_dependency"]
        )
        lore_row.cycle_instability = clamp_0_100(
            lore_row.cycle_instability + delta["cycle_instability"]
        )
        lore_row.player_cross_signature_level = max(
            0, int(lore_row.player_cross_signature_level + delta["player_cross_signature_level"])
        )
        lore_row.protocol_phase = self._phase_for_instability(lore_row.cycle_instability)
        return delta

    def _apply_time_delta(
        self,
        *,
        time_row: GameSlotTimeState,
        text: str,
        story_progress: dict[str, Any] | None,
        battle_summary: dict[str, Any] | None,
    ) -> dict[str, int]:
        delta = {
            "temporal_debt": 0,
            "narrative_cohesion": 0,
            "judicative_stability": 0,
            "compilation_risk": 0,
            "phase3_stripping_progress": 0,
        }
        lowered = text.lower()
        if any(k in lowered for k in ("回响", "既视感", "梦", "循环")):
            delta["temporal_debt"] += 2
            delta["compilation_risk"] += 3
        if any(k in lowered for k in ("矛盾", "冲突", "悖论")):
            delta["narrative_cohesion"] -= 3
            delta["judicative_stability"] -= 2
            delta["phase3_stripping_progress"] += 2
        if battle_summary:
            delta["temporal_debt"] += 2
            delta["narrative_cohesion"] -= 1
        status = (
            str(story_progress.get("objective_status", "pending"))
            if isinstance(story_progress, dict)
            else "pending"
        )
        if status == "completed":
            delta["narrative_cohesion"] += 2
            delta["judicative_stability"] += 1

        time_row.temporal_debt = max(0, int(time_row.temporal_debt + delta["temporal_debt"]))
        time_row.narrative_cohesion = clamp_0_100(
            time_row.narrative_cohesion + delta["narrative_cohesion"]
        )
        time_row.judicative_stability = clamp_0_100(
            time_row.judicative_stability + delta["judicative_stability"]
        )
        time_row.compilation_risk = clamp_0_100(
            time_row.compilation_risk + delta["compilation_risk"]
        )
        time_row.phase3_stripping_progress = clamp_0_100(
            time_row.phase3_stripping_progress + delta["phase3_stripping_progress"]
        )
        return delta

    def _apply_faction_delta(
        self,
        *,
        faction_row: GameSlotFactionState,
        text: str,
        battle_summary: dict[str, Any] | None,
    ) -> dict[str, int]:
        delta = {
            "league_central_stability": 0,
            "league_public_faction_power": 0,
            "league_regional_defiance": 0,
            "white_ring_banist": 0,
            "white_ring_transitionist": 0,
            "white_ring_accelerationist": 0,
            "consortium_governance": 0,
            "consortium_expansion": 0,
            "consortium_substitution": 0,
            "grassroots_mutual_aid": 0,
            "grassroots_militia": 0,
            "grassroots_radicalisation": 0,
            "witnesses_intervention": 0,
            "witnesses_preservation": 0,
            "witnesses_resignation": 0,
        }
        for keyword, patch in faction_rules().get("keyword_delta", {}).items():
            if keyword in text:
                for field, change in patch.items():
                    if field in delta:
                        delta[field] += int(change)
        if battle_summary:
            delta["grassroots_militia"] += 2
            delta["league_regional_defiance"] += 1

        for field, change in delta.items():
            current = int(getattr(faction_row, field))
            setattr(faction_row, field, clamp_0_100(current + int(change)))
        return delta

    def _warnings(
        self,
        *,
        lore_row: GameSlotLoreState,
        time_row: GameSlotTimeState,
    ) -> list[str]:
        out: list[str] = []
        if lore_row.cycle_instability >= 80:
            out.append("cycle_instability_high")
        if time_row.narrative_cohesion <= 40:
            out.append("narrative_cohesion_low")
        if time_row.compilation_risk >= 70:
            out.append("compilation_risk_high")
        return out

    def apply_story_outcome(
        self,
        db: Session,
        *,
        session_obj: StorySession,
        user_text: str,
        assistant_text: str,
        story_progress: dict[str, Any] | None = None,
        battle_summary: dict[str, Any] | None = None,
    ) -> KernelApplyResult:
        slot = self.ensure_slot_for_session(db, session_obj=session_obj)
        lore_row, time_row, faction_row = self.ensure_kernel_rows(db, slot_id=slot.id)

        joint_text = f"{user_text}\n{assistant_text}"
        lore_delta = self._apply_lore_delta(
            lore_row=lore_row,
            text=joint_text,
            battle_summary=battle_summary,
        )
        time_delta = self._apply_time_delta(
            time_row=time_row,
            text=joint_text,
            story_progress=story_progress,
            battle_summary=battle_summary,
        )
        faction_delta = self._apply_faction_delta(
            faction_row=faction_row,
            text=joint_text,
            battle_summary=battle_summary,
        )
        warnings = self._warnings(lore_row=lore_row, time_row=time_row)

        db.add_all([slot, lore_row, time_row, faction_row])
        return KernelApplyResult(
            slot_id=slot.id,
            lore_delta=lore_delta,
            time_delta=time_delta,
            faction_delta=faction_delta,
            active_warnings=warnings,
        )

