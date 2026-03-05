from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GameSlotFactionState, GameSlotLoreState, GameSlotTimeState


class KernelSummaryService:
    def get_rows(
        self,
        db: Session,
        *,
        slot_id: uuid.UUID,
    ) -> tuple[GameSlotLoreState | None, GameSlotTimeState | None, GameSlotFactionState | None]:
        lore = db.execute(
            select(GameSlotLoreState).where(GameSlotLoreState.slot_id == slot_id)
        ).scalar_one_or_none()
        time = db.execute(
            select(GameSlotTimeState).where(GameSlotTimeState.slot_id == slot_id)
        ).scalar_one_or_none()
        faction = db.execute(
            select(GameSlotFactionState).where(GameSlotFactionState.slot_id == slot_id)
        ).scalar_one_or_none()
        return lore, time, faction

    def summarize_lore(self, row: GameSlotLoreState | None) -> dict[str, Any]:
        if row is None:
            return {}
        return {
            "global_balance_index": row.global_balance_index,
            "human_power_dependency": row.human_power_dependency,
            "cycle_instability": row.cycle_instability,
            "protocol_phase": row.protocol_phase.value,
            "player_cross_signature_level": row.player_cross_signature_level,
            "legendary_alignment": row.legendary_alignment or {},
        }

    def summarize_time(self, row: GameSlotTimeState | None) -> dict[str, Any]:
        if row is None:
            return {}
        return {
            "temporal_debt": row.temporal_debt,
            "narrative_cohesion": row.narrative_cohesion,
            "judicative_stability": row.judicative_stability,
            "compilation_risk": row.compilation_risk,
            "phase3_stripping_progress": row.phase3_stripping_progress,
        }

    def summarize_faction(self, row: GameSlotFactionState | None) -> dict[str, Any]:
        if row is None:
            return {}
        payload = {
            "league": {
                "central_stability": row.league_central_stability,
                "public_faction_power": row.league_public_faction_power,
                "regional_defiance": row.league_regional_defiance,
            },
            "white_ring": {
                "banist": row.white_ring_banist,
                "transitionist": row.white_ring_transitionist,
                "accelerationist": row.white_ring_accelerationist,
            },
            "consortium": {
                "governance": row.consortium_governance,
                "expansion": row.consortium_expansion,
                "substitution": row.consortium_substitution,
            },
            "grassroots": {
                "mutual_aid": row.grassroots_mutual_aid,
                "militia": row.grassroots_militia,
                "radicalisation": row.grassroots_radicalisation,
            },
            "witnesses": {
                "intervention": row.witnesses_intervention,
                "preservation": row.witnesses_preservation,
                "resignation": row.witnesses_resignation,
            },
        }
        return payload

    def warnings(
        self,
        *,
        lore: GameSlotLoreState | None,
        time: GameSlotTimeState | None,
    ) -> list[str]:
        out: list[str] = []
        if lore and lore.cycle_instability >= 80:
            out.append("world_tension_extreme")
        if time and time.narrative_cohesion <= 40:
            out.append("narrative_cohesion_low")
        if time and time.compilation_risk >= 70:
            out.append("compilation_risk_high")
        return out

