from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.battle.fast_resolver import is_battle_turn, resolve_fast_battle
from app.canon.fact_checker import (
    build_repair_prompt,
    check_facts,
    extract_structured_json,
    strip_structured_json,
)
from app.core.config import Settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.metrics import (
    rp_option_final_latency_ms,
    rp_provider_latency_seconds,
    rp_retrieval_timeline_hits_total,
    rp_retrieval_vector_hits_total,
    rp_turns_created_total,
)
from app.db.models import AuditLog, CanonPokemon, Turn, User
from app.db.models import Session as StorySession
from app.memory.budgeter import InjectionStats, normalize_pace
from app.memory.compression import compress_retrieval
from app.memory.prompt_assembler import assemble_messages
from app.memory.query_builder import build_query_plan
from app.memory.retriever import retrieve_memory
from app.memory.schemas import EmbeddingProvider, QueryPlan
from app.memory.writer import write_memory
from app.providers.base import LLMProvider
from app.services.action_option_service import ActionOptionService
from app.services.story_progress_service import StoryProgressService
from app.services.v2.kernel_summary_service import KernelSummaryService
from app.services.v2.story_state_engine import StoryStateEngine
from app.utils.sse import sse_event

logger = get_logger(__name__)

ENGLISH_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9'/-]{2,}\b")
PAREN_EN_RE = re.compile(r"[（(]\s*[A-Za-z0-9 ,./'_-]{2,}\s*[）)]")
CJK_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}")

INVENTORY_CATEGORIES = {
    "balls": "精灵球",
    "medicine": "回复药",
    "battle_items": "战斗道具",
    "berries": "树果",
    "key_items": "关键道具",
    "materials": "素材",
    "misc": "杂项",
}


@dataclass
class ChatResult:
    turn_id: str
    turn_index: int
    assistant_text: str
    narrative: dict[str, str] | None
    provider_latency_ms: int
    token_usage: dict[str, int] | None
    action_options: list[dict[str, str]]
    battle_summary: dict | None
    state_update: dict[str, Any]
    player_state: dict[str, Any]
    kernel_delta_summary: dict[str, Any] | None
    time_class_applied: str | None


@dataclass
class PreparedGeneration:
    query_plan: QueryPlan
    query_plan_payload: list[dict[str, str]]
    messages: list[dict[str, str]]
    injection_block: str
    injection_stats: InjectionStats
    pace: str


class ChatService:
    def __init__(
        self,
        *,
        settings: Settings,
        provider: LLMProvider,
        embedding_provider: EmbeddingProvider,
    ):
        self.settings = settings
        self.provider = provider
        self.embedding_provider = embedding_provider
        self.action_option_service = ActionOptionService()
        self.story_progress_service = StoryProgressService()
        self.story_state_engine = StoryStateEngine()
        self.kernel_summary_service = KernelSummaryService()

    def _load_session_or_raise(
        self,
        db: Session,
        *,
        session_id: uuid.UUID,
        current_user: User,
    ) -> StorySession:
        session_obj = db.execute(
            select(StorySession).where(
                StorySession.id == session_id, StorySession.deleted.is_(False)
            )
        ).scalar_one_or_none()
        if not session_obj:
            raise AppError(code="session_not_found", message="Session not found", status_code=404)
        if session_obj.user_id != current_user.id and current_user.role.value not in {
            "admin",
            "operator",
        }:
            raise AppError(code="forbidden", message="No access to this session", status_code=403)
        return session_obj

    def _next_turn_index(self, db: Session, session_id: uuid.UUID) -> int:
        latest = db.execute(
            select(Turn)
            .where(Turn.session_id == session_id)
            .order_by(desc(Turn.turn_index))
            .limit(1)
        ).scalar_one_or_none()
        return (latest.turn_index + 1) if latest else 1

    def _audit(
        self,
        db: Session,
        *,
        session_id: uuid.UUID,
        turn_id: uuid.UUID | None,
        action: str,
        payload: dict,
    ) -> None:
        db.add(AuditLog(session_id=session_id, turn_id=turn_id, action=action, payload=payload))

    def _kernel_capsule(
        self,
        db: Session,
        *,
        session_obj: StorySession,
    ) -> tuple[dict[str, Any], str]:
        slot = self.story_state_engine.ensure_slot_for_session(db, session_obj=session_obj)
        self.story_state_engine.ensure_kernel_rows(db, slot_id=slot.id)
        lore_row, time_row, faction_row = self.kernel_summary_service.get_rows(db, slot_id=slot.id)
        lore = self.kernel_summary_service.summarize_lore(lore_row)
        time_state = self.kernel_summary_service.summarize_time(time_row)
        faction = self.kernel_summary_service.summarize_faction(faction_row)
        warnings = self.kernel_summary_service.warnings(lore=lore_row, time=time_row)

        faction_flat: list[tuple[str, int]] = []
        for group_name, group in faction.items():
            if isinstance(group, dict):
                for k, v in group.items():
                    if isinstance(v, int):
                        faction_flat.append((f"{group_name}.{k}", v))
        faction_flat.sort(key=lambda x: x[1], reverse=True)
        top_pressure = faction_flat[:3]

        lines = [
            "【KERNEL_CAPSULE】",
            f"- protocol_phase: {lore.get('protocol_phase', 'silent_sampling')}",
            f"- cycle_instability: {lore.get('cycle_instability', 0)}",
            f"- global_balance_index: {lore.get('global_balance_index', 0)}",
            f"- temporal_debt: {time_state.get('temporal_debt', 0)}",
            f"- narrative_cohesion: {time_state.get('narrative_cohesion', 0)}",
            f"- compilation_risk: {time_state.get('compilation_risk', 0)}",
            "- faction_pressure_top3: "
            + (", ".join(f"{name}:{value}" for name, value in top_pressure) or "none"),
            "- active_warnings: " + (", ".join(warnings) if warnings else "none"),
        ]
        return (
            {
                "slot_id": str(slot.id),
                "lore": lore,
                "time": time_state,
                "faction": faction,
                "warnings": warnings,
            },
            "\n".join(lines),
        )

    def _prepare_generation(
        self,
        *,
        db: Session,
        session_obj: StorySession,
        user_text: str,
        language: str,
        pace: str = "balanced",
    ) -> PreparedGeneration:
        t0 = time.perf_counter()
        query_plan = build_query_plan(user_text)
        query_plan_payload = [{"type": q.type.value, "q": q.q} for q in query_plan.queries]
        self._audit(
            db,
            session_id=session_obj.id,
            turn_id=None,
            action="query_builder",
            payload={"queries": query_plan_payload},
        )

        t1 = time.perf_counter()
        query_embeddings = self.embedding_provider.embed([q.q for q in query_plan.queries])
        retrieval = retrieve_memory(
            db,
            session_id=session_obj.id,
            query_plan=query_plan,
            query_embeddings=query_embeddings,
            settings=self.settings,
        )
        rp_retrieval_vector_hits_total.inc(retrieval.debug.vector_hits)
        rp_retrieval_timeline_hits_total.inc(retrieval.debug.timeline_hits)

        retrieval = compress_retrieval(retrieval, self.settings)
        self._audit(
            db,
            session_id=session_obj.id,
            turn_id=None,
            action="retrieval",
            payload={
                "canon_count": len(retrieval.canon_facts),
                "recall_count": len(retrieval.recalls),
                "queries": query_plan_payload,
                "recalls": [
                    {"chunk_id": r.chunk_id, "score": r.score, "turn_index": r.turn_index}
                    for r in retrieval.recalls
                ],
            },
        )

        recent_turns = list(
            db.execute(
                select(Turn)
                .where(Turn.session_id == session_obj.id)
                .order_by(desc(Turn.turn_index))
                .limit(self.settings.short_window_turns)
            )
            .scalars()
            .all()
        )
        recent_turns.reverse()

        battle_hint = None
        if session_obj.battle_mode == "fast" and is_battle_turn(user_text):
            battle_hint = "检测到战斗场景，请按 fast 模式输出简短战斗结果与下一步建议。"

        t2 = time.perf_counter()
        normalized_pace = normalize_pace(pace)
        messages, injection_block, injection_stats = assemble_messages(
            session_obj,
            user_text,
            query_plan,
            retrieval,
            recent_turns,
            self.settings,
            battle_mode=session_obj.battle_mode,
            battle_hint=battle_hint,
            pace=normalized_pace,
        )
        kernel_state, kernel_capsule_text = self._kernel_capsule(db, session_obj=session_obj)
        messages.insert(-1, {"role": "system", "content": kernel_capsule_text})
        if isinstance(session_obj.player_state, dict):
            session_obj.player_state["kernel_summary"] = kernel_state
        if language == "zh":
            messages.insert(
                -1,
                {
                    "role": "system",
                    "content": (
                        "本轮输出语言要求：简体中文优先。"
                        "剧情正文和【可选动作】只使用中文，不要英文名或中英混写。"
                        "若必须提及外文名，仅在首次出现用“中文名（English）”格式。"
                    ),
                },
            )
        elif language == "bilingual":
            messages.insert(
                -1,
                {
                    "role": "system",
                    "content": "本轮输出可中英双语，但优先中文叙事。",
                },
            )
        self._audit(
            db,
                session_id=session_obj.id,
                turn_id=None,
                action="prompt_assembled",
                payload={
                    "injection": injection_block,
                    "battle_hint": bool(battle_hint),
                    "pace": normalized_pace,
                    "injection_stats": {
                        "estimated_tokens": injection_stats.estimated_tokens,
                        "sections_used": injection_stats.sections_used,
                        "sections_trimmed": injection_stats.sections_trimmed,
                        "quality_mode": injection_stats.quality_mode,
                    },
                },
            )

        t3 = time.perf_counter()
        logger.info(
            "memory_prepared",
            session_id=str(session_obj.id),
            query_count=len(query_plan.queries),
            canon_count=len(retrieval.canon_facts),
            recall_count=len(retrieval.recalls),
            query_ms=int((t1 - t0) * 1000),
            retrieve_ms=int((t2 - t1) * 1000),
            assemble_ms=int((t3 - t2) * 1000),
        )

        return PreparedGeneration(
            query_plan=query_plan,
            query_plan_payload=query_plan_payload,
            messages=messages,
            injection_block=injection_block,
            injection_stats=injection_stats,
            pace=normalized_pace,
        )

    def _extract_action_options(
        self,
        structured_payload: dict,
        assistant_text: str,
    ) -> list[dict[str, str]]:
        return self.action_option_service.extract_action_options(structured_payload, assistant_text)

    def _normalize_language(self, language: str | None) -> str:
        v = (language or "zh").strip().lower()
        if v in {"zh", "cn", "zh-cn", "中文", "chinese"}:
            return "zh"
        if v in {"en", "english", "bilingual", "bi"}:
            return "bilingual"
        return "zh"

    def _build_layered_narrative(self, assistant_text: str) -> dict[str, str]:
        cleaned = (self._remove_json_leakage(assistant_text) or assistant_text).strip()
        if not cleaned:
            return {"primary": ""}
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if not lines:
            return {"primary": cleaned}
        primary_lines: list[str] = []
        char_budget = 320
        char_used = 0
        for line in lines:
            if len(primary_lines) >= 6:
                break
            if primary_lines and char_used + len(line) > char_budget:
                break
            primary_lines.append(line)
            char_used += len(line)
        primary = "\n".join(primary_lines).strip() if primary_lines else cleaned[:char_budget]
        if primary == cleaned:
            return {"primary": primary}
        return {"primary": primary, "detail": cleaned}

    def _remove_json_leakage(self, text: str) -> str:
        if not text:
            return text
        lowered = text.lower()
        marker = lowered.find("```json")
        if marker >= 0:
            return text[:marker].rstrip()
        marker = text.find("<!--JSON-->")
        if marker >= 0:
            return text[:marker].rstrip()
        marker = lowered.find("`json")
        if marker >= 0 and "facts_used" in lowered[marker:]:
            return text[:marker].rstrip()
        if "\"facts_used\"" in lowered and "{" in text:
            first = text.find("{")
            if first >= 0:
                return text[:first].rstrip()
        return text

    def _prefer_chinese_text(self, text: str, *, aggressive: bool = False) -> str:
        if not text:
            return text
        out = PAREN_EN_RE.sub("", text)
        if aggressive:
            out = ENGLISH_WORD_RE.sub("", out)
            out = re.sub(r"\s{2,}", " ", out)
            out = out.replace(" ,", ",").strip()
        return out

    def _extract_name_token(self, item: Any) -> str:
        if isinstance(item, str):
            return self._normalize_name_token(item)
        if isinstance(item, dict):
            for key in ("name_zh", "name", "species", "slug_id", "id"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return self._normalize_name_token(value)
        return ""

    def _normalize_name_token(self, token: str) -> str:
        text = token.strip()
        if not text:
            return ""
        cjk_parts = CJK_TOKEN_RE.findall(text)
        if cjk_parts:
            cjk_parts.sort(key=len, reverse=True)
            return cjk_parts[0]
        text = PAREN_EN_RE.sub("", text)
        text = re.sub(r"\s+", " ", text).strip()
        for sep in (" / ", "/", ",", "，", ";", "；", "|"):
            if sep in text:
                text = text.split(sep, 1)[0].strip()
        if " " in text:
            text = text.split(" ", 1)[0].strip()
        return text

    def _best_zh_name(self, row: CanonPokemon) -> str:
        def has_han(value: str) -> bool:
            return bool(re.search(r"[\u4e00-\u9fff]", value))

        def has_kana_or_hangul(value: str) -> bool:
            return bool(re.search(r"[\u3040-\u30ff\uac00-\ud7af]", value))

        primary = str(row.name_zh or "").strip()
        if primary and has_han(primary) and not has_kana_or_hangul(primary):
            return primary
        for alias in row.aliases or []:
            if isinstance(alias, str):
                candidate = alias.strip()
                if candidate and has_han(candidate) and not has_kana_or_hangul(candidate):
                    return candidate
        for alias in row.aliases or []:
            if isinstance(alias, str):
                candidate = alias.strip()
                if candidate and has_han(candidate):
                    return candidate
        if primary:
            return primary
        name_en = str(row.name_en or "").strip()
        return name_en or row.slug_id

    def _resolve_pokemon_entry(
        self,
        db: Session,
        *,
        session_obj: StorySession,
        item: Any,
    ) -> dict[str, Any] | None:
        token = self._extract_name_token(item)
        if not token:
            return None

        token_lower = token.lower()
        row = db.execute(
            select(CanonPokemon).where(
                CanonPokemon.generation <= session_obj.canon_gen,
                func.lower(CanonPokemon.slug_id) == token_lower,
            )
        ).scalar_one_or_none()
        if row is None:
            row = db.execute(
                select(CanonPokemon).where(
                    CanonPokemon.generation <= session_obj.canon_gen,
                    func.lower(CanonPokemon.name_en) == token_lower,
                )
            ).scalar_one_or_none()
        if row is None:
            row = db.execute(
                select(CanonPokemon).where(
                    CanonPokemon.generation <= session_obj.canon_gen,
                    CanonPokemon.name_zh == token,
                )
            ).scalar_one_or_none()
        if row is None:
            rows = list(
                db.execute(
                    select(CanonPokemon).where(CanonPokemon.generation <= session_obj.canon_gen)
                )
                .scalars()
                .all()
            )
            token_lower = token.lower()
            for candidate in rows:
                aliases = candidate.aliases or []
                if any(
                    isinstance(alias, str) and alias.strip().lower() == token_lower
                    for alias in aliases
                ):
                    row = candidate
                    break

        if row is not None:
            level = item.get("level") if isinstance(item, dict) else None
            status = None
            if isinstance(item, dict):
                status = item.get("condition") or item.get("status") or item.get("notes")
            return {
                "slug_id": row.slug_id,
                "name_zh": self._best_zh_name(row),
                "types": row.types or [],
                "level": int(level) if isinstance(level, int) else 5,
                "status": str(status)[:80] if isinstance(status, str) else "",
            }

        return {
            "slug_id": token_lower.replace(" ", "-"),
            "name_zh": token,
            "types": [],
            "level": 5,
            "status": "",
        }

    def _inventory_bucket(self, key: str) -> str:
        lk = key.lower()
        if "ball" in lk or "球" in lk:
            return "balls"
        if "药" in lk or "heal" in lk or "potion" in lk or "medicine" in lk:
            return "medicine"
        if "berry" in lk or "树果" in lk:
            return "berries"
        if "key" in lk or "关键" in lk:
            return "key_items"
        if "battle" in lk or "战斗" in lk:
            return "battle_items"
        if "material" in lk or "素材" in lk:
            return "materials"
        return "misc"

    def _normalize_inventory(self, value: Any) -> dict[str, Any]:
        normalized: dict[str, Any] = {k: [] for k in INVENTORY_CATEGORIES}
        if not isinstance(value, dict):
            return normalized
        for key, item in value.items():
            bucket = self._inventory_bucket(key)
            if isinstance(item, int):
                if item <= 0:
                    continue
                normalized[bucket].append({"name_zh": INVENTORY_CATEGORIES[bucket], "count": item})
            elif isinstance(item, str):
                if not item.strip():
                    continue
                normalized[bucket].append({"name_zh": item.strip(), "count": 1})
            elif isinstance(item, list):
                for entry in item:
                    if isinstance(entry, str) and entry.strip():
                        normalized[bucket].append({"name_zh": entry.strip(), "count": 1})
                    elif isinstance(entry, dict):
                        name = str(entry.get("name_zh") or entry.get("name") or entry.get("slug_id") or "").strip()
                        if not name:
                            continue
                        count = entry.get("count")
                        qty = int(count) if isinstance(count, int) and count > 0 else 1
                        normalized[bucket].append({"name_zh": name, "count": qty})
            elif isinstance(item, dict):
                for n, c in item.items():
                    name = str(n).strip()
                    if not name:
                        continue
                    qty = int(c) if isinstance(c, int) and c > 0 else 1
                    normalized[bucket].append({"name_zh": name, "count": qty})
        return normalized

    def _normalize_state_update(
        self,
        db: Session,
        *,
        session_obj: StorySession,
        state_update: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(state_update, dict):
            return {}

        base_state = session_obj.player_state if isinstance(session_obj.player_state, dict) else {}
        normalized: dict[str, Any] = {}

        for key in ("location", "player_location", "current_location"):
            value = state_update.get(key)
            if isinstance(value, str) and value.strip():
                normalized["location"] = value.strip()
                break

        for key in ("money", "coins", "gold"):
            value = state_update.get(key)
            if isinstance(value, int):
                normalized["money"] = value
                break

        badges = state_update.get("badges")
        if isinstance(badges, list):
            normalized["badges"] = [str(b).strip() for b in badges if str(b).strip()]

        team_seed: list[Any] = []
        for key in ("team", "party", "party_status", "pokemon_team", "captured_pokemon", "new_pokemon"):
            value = state_update.get(key)
            if isinstance(value, list):
                team_seed.extend(value)
        team: list[dict[str, Any]] = []
        existing_team = base_state.get("team", []) if isinstance(base_state, dict) else []
        if isinstance(existing_team, list):
            for item in existing_team:
                resolved = self._resolve_pokemon_entry(db, session_obj=session_obj, item=item)
                if resolved:
                    team.append(resolved)
        for item in team_seed:
            resolved = self._resolve_pokemon_entry(db, session_obj=session_obj, item=item)
            if resolved:
                team.append(resolved)
        if team:
            dedup: dict[str, dict[str, Any]] = {}
            for item in team:
                dedup[item["slug_id"]] = item
            normalized["team"] = list(dedup.values())

        box_seed = state_update.get("storage_box") or state_update.get("pokemon_box")
        if isinstance(box_seed, list):
            box: list[dict[str, Any]] = []
            existing_box = base_state.get("storage_box", []) if isinstance(base_state, dict) else []
            if isinstance(existing_box, list):
                for item in existing_box:
                    resolved = self._resolve_pokemon_entry(db, session_obj=session_obj, item=item)
                    if resolved:
                        box.append(resolved)
            for item in box_seed:
                resolved = self._resolve_pokemon_entry(db, session_obj=session_obj, item=item)
                if resolved:
                    box.append(resolved)
            if box:
                dedup = {item["slug_id"]: item for item in box}
                normalized["storage_box"] = list(dedup.values())

        inv_source = state_update.get("inventory")
        if isinstance(inv_source, dict):
            normalized["inventory"] = self._normalize_inventory(inv_source)
        else:
            root_inv = {
                k: v
                for k, v in state_update.items()
                if any(
                    token in k.lower()
                    for token in ("ball", "berry", "potion", "medicine", "item", "道具", "球", "药")
                )
            }
            if root_inv:
                normalized["inventory"] = self._normalize_inventory(root_inv)

        quests = state_update.get("quests")
        if isinstance(quests, list):
            normalized["quests"] = [str(q).strip() for q in quests if str(q).strip()]

        for passthrough in ("relationship", "phase", "special_quest"):
            if passthrough in state_update:
                normalized[passthrough] = state_update[passthrough]

        return normalized

    def _apply_roster_limits(self, state: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(state, dict):
            return state
        team = state.get("team", [])
        box = state.get("storage_box", [])
        if not isinstance(team, list):
            team = []
        if not isinstance(box, list):
            box = []

        dedup_team: dict[str, dict[str, Any]] = {}
        for item in team:
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug_id") or item.get("name_zh") or "").strip()
            if not slug:
                continue
            dedup_team[slug] = item
        ordered_team = list(dedup_team.values())

        overflow = ordered_team[6:]
        limited_team = ordered_team[:6]
        if overflow:
            box = [*box, *overflow]

        dedup_box: dict[str, dict[str, Any]] = {}
        for item in box:
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug_id") or item.get("name_zh") or "").strip()
            if not slug or slug in {t.get("slug_id") for t in limited_team if isinstance(t, dict)}:
                continue
            dedup_box[slug] = item

        state["team"] = limited_team
        state["storage_box"] = list(dedup_box.values())
        return state

    def _extract_state_update(self, structured_payload: dict) -> dict[str, Any]:
        raw = structured_payload.get("state_update") if isinstance(structured_payload, dict) else None
        if isinstance(raw, dict):
            return raw
        return {}

    def _merge_state(self, base: Any, patch: Any) -> Any:
        if isinstance(base, dict) and isinstance(patch, dict):
            merged: dict[str, Any] = dict(base)
            for key, value in patch.items():
                merged[key] = self._merge_state(merged.get(key), value)
            return merged
        return patch if patch is not None else base

    def _chapter_lookup(self, world_profile: dict[str, Any]) -> dict[int, dict[str, Any]]:
        return self.story_progress_service._chapter_lookup(world_profile)

    def _apply_story_progress(
        self,
        *,
        session_obj: StorySession,
        merged_state: dict[str, Any],
        user_text: str,
        assistant_text: str,
    ) -> dict[str, Any]:
        return self.story_progress_service.apply_story_progress(
            session_obj=session_obj,
            merged_state=merged_state,
            user_text=user_text,
            assistant_text=assistant_text,
        )

    @staticmethod
    def _looks_ascii_name(value: str) -> bool:
        if not value:
            return False
        return all(ord(ch) < 128 for ch in value)

    def _replace_name_token(self, text: str, token: str, replacement: str) -> str:
        if not token or token == replacement:
            return text
        pattern = re.compile(
            rf"(?<![A-Za-z0-9_-]){re.escape(token)}(?![A-Za-z0-9_-])",
            flags=re.IGNORECASE,
        )
        return pattern.sub(replacement, text)

    def _localize_pokemon_names(
        self,
        *,
        db: Session,
        session_obj: StorySession,
        structured_payload: dict,
        user_text: str,
        language: str,
        assistant_text: str,
        action_options: list[dict[str, str]],
    ) -> tuple[str, list[dict[str, str]]]:
        slugs: set[str] = set()
        facts = structured_payload.get("facts_used") if isinstance(structured_payload, dict) else None
        if isinstance(facts, list):
            for fact in facts:
                if not isinstance(fact, dict):
                    continue
                if str(fact.get("kind", "")).lower() != "pokemon":
                    continue
                slug = str(fact.get("slug") or fact.get("id") or "").strip().lower()
                if slug:
                    slugs.add(slug)

        for starter in session_obj.starter_options or []:
            if isinstance(starter, dict):
                slug = str(starter.get("slug_id") or "").strip().lower()
                if slug:
                    slugs.add(slug)

        team = session_obj.player_state.get("team", []) if isinstance(session_obj.player_state, dict) else []
        if isinstance(team, list):
            for item in team:
                if isinstance(item, dict):
                    slug = str(item.get("slug_id") or item.get("id") or "").strip().lower()
                    if slug:
                        slugs.add(slug)
                elif isinstance(item, str):
                    slugs.add(item.strip().lower())

        for token in {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", user_text)}:
            row = db.execute(
                select(CanonPokemon).where(func.lower(CanonPokemon.slug_id) == token)
            ).scalar_one_or_none()
            if row is None:
                row = db.execute(
                    select(CanonPokemon).where(func.lower(CanonPokemon.name_en) == token)
                ).scalar_one_or_none()
            if row is not None:
                slugs.add(row.slug_id.lower())

        if not slugs:
            return assistant_text, action_options

        rows = list(
            db.execute(select(CanonPokemon).where(CanonPokemon.slug_id.in_(sorted(slugs)))).scalars().all()
        )
        if not rows:
            return assistant_text, action_options

        localized_text = assistant_text
        localized_options = [dict(item) for item in action_options]

        for row in rows:
            zh_name = self._best_zh_name(row)
            if not zh_name:
                continue
            candidates = {row.slug_id, row.name_en}
            for alias in row.aliases or []:
                if isinstance(alias, str) and self._looks_ascii_name(alias):
                    candidates.add(alias)

            for token in sorted(candidates, key=len, reverse=True):
                if not token:
                    continue
                localized_text = self._replace_name_token(localized_text, token, zh_name)
                for option in localized_options:
                    option["text"] = self._replace_name_token(option.get("text", ""), token, zh_name)
                    option["send_text"] = self._replace_name_token(
                        option.get("send_text", ""), token, zh_name
                    )

        if language == "zh":
            localized_text = self._prefer_chinese_text(localized_text, aggressive=False)
            for option in localized_options:
                option["text"] = self._prefer_chinese_text(option.get("text", ""), aggressive=True)
                option["send_text"] = self._prefer_chinese_text(
                    option.get("send_text", ""), aggressive=True
                )

        return localized_text, localized_options

    async def _repair_if_needed(
        self,
        *,
        db: Session,
        session_id: uuid.UUID,
        messages: list[dict[str, str]],
        output: str,
        allow_model_repair: bool = True,
        repair_issue_limit: int | None = None,
    ) -> tuple[str, dict, bool]:
        structured = extract_structured_json(output, strict=True)
        structured_payload = structured if isinstance(structured, dict) else {}
        facts_used = (
            structured_payload.get("facts_used", [])
            if isinstance(structured_payload.get("facts_used", []), list)
            else []
        )
        fact_result = check_facts(db, session_id=session_id, facts_used=facts_used)
        if fact_result.ok:
            return output, structured_payload, False

        if repair_issue_limit is not None and len(fact_result.issues) > repair_issue_limit:
            logger.warning(
                "canon_repair_skipped_too_many_issues",
                session_id=str(session_id),
                issue_count=len(fact_result.issues),
                repair_issue_limit=repair_issue_limit,
            )
            return output, structured_payload, False

        if not allow_model_repair:
            logger.warning(
                "canon_repair_skipped",
                session_id=str(session_id),
                issue_count=len(fact_result.issues),
                mode="disabled_for_turn",
            )
            return output, structured_payload, False

        repair_prompt = build_repair_prompt(fact_result.issues)
        repaired_messages = messages + [{"role": "system", "content": repair_prompt}]
        repaired = await self.provider.generate(repaired_messages, stream=False)
        if isinstance(repaired, str):
            repaired_structured = extract_structured_json(repaired)
            repaired_payload = repaired_structured if isinstance(repaired_structured, dict) else {}
            logger.warning(
                "canon_repair_applied",
                session_id=str(session_id),
                issues=len(fact_result.issues),
            )
            return repaired, repaired_payload, True

        return output, structured_payload, False

    async def generate_once(
        self,
        *,
        db: Session,
        session_obj: StorySession,
        user_text: str,
        language: str,
    ) -> tuple[
        str,
        dict,
        str,
        list[dict],
        QueryPlan,
        list[dict[str, str]],
        dict | None,
        dict[str, Any],
    ]:
        prepared = self._prepare_generation(
            db=db, session_obj=session_obj, user_text=user_text, language=language
        )
        output = await self.provider.generate(prepared.messages, stream=False)
        assert isinstance(output, str)

        final_text, structured, _repaired = await self._repair_if_needed(
            db=db,
            session_id=session_obj.id,
            messages=prepared.messages,
            output=output,
        )
        cleaned_text = strip_structured_json(final_text) or final_text
        cleaned_text = self._remove_json_leakage(cleaned_text) or cleaned_text
        action_options = self._extract_action_options(structured, cleaned_text)
        state_update = self._extract_state_update(structured)
        state_update = self._normalize_state_update(
            db,
            session_obj=session_obj,
            state_update=state_update,
        )
        cleaned_text, action_options = self._localize_pokemon_names(
            db=db,
            session_obj=session_obj,
            structured_payload=structured,
            user_text=user_text,
            language=language,
            assistant_text=cleaned_text,
            action_options=action_options,
        )

        battle = resolve_fast_battle(
            session_obj=session_obj,
            user_text=user_text,
            assistant_text=cleaned_text,
        )
        battle_summary = battle.summary if battle.triggered else None
        if battle_summary and battle_summary.get("battle_text"):
            cleaned_text = f"{cleaned_text}{battle_summary['battle_text']}"

        if not action_options and battle.triggered:
            next_options = (
                battle_summary.get("next_options", [])
                if isinstance(battle_summary, dict)
                else []
            )
            action_options = (
                next_options
                if isinstance(next_options, list) and next_options
                else [
                    {"id": "battle-heal", "text": "先补给并稳住阵型", "send_text": "我先补给并稳住阵型"},
                    {"id": "battle-press", "text": "继续追击压制对手", "send_text": "我选择继续追击压制"},
                    {"id": "battle-switch", "text": "换位并观察对手弱点", "send_text": "我先换位并观察弱点"},
                ]
            )

        return (
            cleaned_text,
            structured,
            prepared.injection_block,
            prepared.query_plan_payload,
            prepared.query_plan,
            action_options,
            battle_summary,
            state_update,
        )

    def _persist_turn(
        self,
        *,
        db: Session,
        session_obj: StorySession,
        user_text: str,
        assistant_text: str,
        action_options: list[dict[str, str]],
        battle_summary: dict | None,
        state_update: dict[str, Any],
        query_plan: QueryPlan,
        query_plan_payload: list[dict],
    ) -> tuple[Turn, dict[str, Any], dict[str, Any], str | None]:
        turn_index = self._next_turn_index(db, session_obj.id)
        metrics = self.provider.last_metrics

        turn = Turn(
            session_id=session_obj.id,
            turn_index=turn_index,
            user_text=user_text,
            assistant_text=assistant_text,
            provider_latency_ms=metrics.latency_ms if metrics else None,
            token_usage=metrics.token_usage if metrics else None,
            action_options=action_options,
            battle_summary=battle_summary,
            state_update=state_update,
        )
        db.add(turn)
        db.flush()

        write_result = write_memory(
            db,
            session_id=session_obj.id,
            turn=turn,
            query_plan=query_plan,
            embedding_provider=self.embedding_provider,
        )

        merged_state = self._merge_state(session_obj.player_state or {}, state_update)
        if not isinstance(merged_state, dict):
            merged_state = session_obj.player_state or {}
        merged_state = self._apply_story_progress(
            session_obj=session_obj,
            merged_state=merged_state,
            user_text=user_text,
            assistant_text=assistant_text,
        )
        merged_state = self._apply_roster_limits(merged_state)
        kernel_apply = self.story_state_engine.apply_story_outcome(
            db,
            session_obj=session_obj,
            user_text=user_text,
            assistant_text=assistant_text,
            story_progress=(
                merged_state.get("story_progress", {})
                if isinstance(merged_state.get("story_progress"), dict)
                else {}
            ),
            battle_summary=battle_summary,
        )
        slot_id = uuid.UUID(str(kernel_apply.slot_id))
        lore_row, time_row, faction_row = self.kernel_summary_service.get_rows(db, slot_id=slot_id)
        merged_state["kernel_summary"] = {
            "lore": self.kernel_summary_service.summarize_lore(lore_row),
            "time": self.kernel_summary_service.summarize_time(time_row),
            "faction": self.kernel_summary_service.summarize_faction(faction_row),
            "warnings": kernel_apply.active_warnings,
        }
        session_obj.player_state = merged_state
        session_obj.updated_at = turn.created_at
        self._audit(
            db,
            session_id=session_obj.id,
            turn_id=turn.id,
            action="turn_committed",
            payload={
                "turn_index": turn_index,
                "query_plan": query_plan_payload,
                "action_options_count": len(action_options),
                "battle_mode": session_obj.battle_mode,
                "has_battle_summary": bool(battle_summary),
                "state_update_keys": sorted(state_update.keys()),
                "kernel_delta_summary": {
                    "lore": kernel_apply.lore_delta,
                    "time": kernel_apply.time_delta,
                    "faction": kernel_apply.faction_delta,
                    "warnings": kernel_apply.active_warnings,
                },
                "time_classes": write_result.time_classes,
                "story_progress": (
                    merged_state.get("story_progress", {})
                    if isinstance(merged_state.get("story_progress"), dict)
                    else {}
                ),
            },
        )
        db.add(session_obj)
        db.commit()
        db.refresh(turn)

        rp_turns_created_total.inc()
        if metrics:
            rp_provider_latency_seconds.labels(provider=metrics.provider).observe(
                metrics.latency_ms / 1000.0
            )

        logger.info(
            "turn_created",
            session_id=str(session_obj.id),
            turn_id=str(turn.id),
            turn_index=turn_index,
            provider_latency=metrics.latency_ms if metrics else None,
            token_usage=metrics.token_usage if metrics else None,
        )
        time_class_applied = write_result.time_classes[0] if write_result.time_classes else None
        return (
            turn,
            merged_state,
            {
                "lore": kernel_apply.lore_delta,
                "time": kernel_apply.time_delta,
                "faction": kernel_apply.faction_delta,
                "warnings": kernel_apply.active_warnings,
            },
            time_class_applied,
        )

    async def chat(
        self,
        *,
        db: Session,
        current_user: User,
        session_id: uuid.UUID,
        user_text: str,
        language: str = "zh",
    ) -> ChatResult:
        session_obj = self._load_session_or_raise(
            db, session_id=session_id, current_user=current_user
        )
        language = self._normalize_language(language)
        (
            assistant_text,
            _structured,
            _injection,
            query_plan_payload,
            query_plan,
            action_options,
            battle_summary,
            state_update,
        ) = await self.generate_once(
            db=db,
            session_obj=session_obj,
            user_text=user_text,
            language=language,
        )
        turn, player_state, kernel_delta_summary, time_class_applied = self._persist_turn(
            db=db,
            session_obj=session_obj,
            user_text=user_text,
            assistant_text=assistant_text,
            action_options=action_options,
            battle_summary=battle_summary,
            state_update=state_update,
            query_plan_payload=query_plan_payload,
            query_plan=query_plan,
        )
        metrics = self.provider.last_metrics
        return ChatResult(
            turn_id=str(turn.id),
            turn_index=turn.turn_index,
            assistant_text=assistant_text,
            narrative=self._build_layered_narrative(assistant_text),
            provider_latency_ms=metrics.latency_ms if metrics else 0,
            token_usage=metrics.token_usage if metrics else None,
            action_options=action_options,
            battle_summary=battle_summary,
            state_update=state_update,
            player_state=player_state,
            kernel_delta_summary=kernel_delta_summary,
            time_class_applied=time_class_applied,
        )

    async def chat_stream(
        self,
        *,
        db: Session,
        current_user: User,
        session_id: uuid.UUID,
        user_text: str,
        language: str = "zh",
    ) -> AsyncIterator[str]:
        try:
            stream_start = time.perf_counter()
            session_obj = self._load_session_or_raise(
                db, session_id=session_id, current_user=current_user
            )
            language = self._normalize_language(language)
            prepared = self._prepare_generation(
                db=db,
                session_obj=session_obj,
                user_text=user_text,
                language=language,
            )
            output = await self.provider.generate(prepared.messages, stream=True)
            chunks: list[str] = []

            if isinstance(output, str):
                for i in range(0, len(output), 80):
                    await asyncio.sleep(0)
                    chunk = output[i : i + 80]
                    chunks.append(chunk)
                    yield sse_event("delta", {"turn_id": "", "text": chunk})
            else:
                async for chunk in output:
                    if not chunk:
                        continue
                    chunks.append(chunk)
                    yield sse_event("delta", {"turn_id": "", "text": chunk})

            assistant_text = "".join(chunks)
            final_text, structured, repaired = await self._repair_if_needed(
                db=db,
                session_id=session_obj.id,
                messages=prepared.messages,
                output=assistant_text,
            )
            cleaned_text = strip_structured_json(final_text) or final_text
            cleaned_text = self._remove_json_leakage(cleaned_text) or cleaned_text
            action_options = self._extract_action_options(structured, cleaned_text)
            state_update = self._extract_state_update(structured)
            state_update = self._normalize_state_update(
                db,
                session_obj=session_obj,
                state_update=state_update,
            )
            cleaned_text, action_options = self._localize_pokemon_names(
                db=db,
                session_obj=session_obj,
                structured_payload=structured,
                user_text=user_text,
                language=language,
                assistant_text=cleaned_text,
                action_options=action_options,
            )

            battle = resolve_fast_battle(
                session_obj=session_obj,
                user_text=user_text,
                assistant_text=cleaned_text,
            )
            battle_summary = battle.summary if battle.triggered else None
            if battle_summary and battle_summary.get("battle_text"):
                battle_text = str(battle_summary["battle_text"])
                cleaned_text = f"{cleaned_text}{battle_text}"
                yield sse_event("delta", {"turn_id": "", "text": battle_text})

            if not action_options and battle.triggered:
                next_options = (
                    battle_summary.get("next_options", [])
                    if isinstance(battle_summary, dict)
                else []
                )
                action_options = (
                    next_options
                    if isinstance(next_options, list) and next_options
                    else [
                        {"id": "battle-heal", "text": "先补给并稳住阵型", "send_text": "我先补给并稳住阵型"},
                        {"id": "battle-press", "text": "继续追击压制对手", "send_text": "我选择继续追击压制"},
                        {"id": "battle-switch", "text": "换位并观察对手弱点", "send_text": "我先换位并观察弱点"},
                    ]
                )

            if repaired:
                yield sse_event(
                    "delta",
                    {
                        "turn_id": "",
                        "text": "\n\n【系统提示】已根据 Canon 数据修正本轮输出并写入最终版本。",
                    },
                )

            (
                turn,
                player_state,
                kernel_delta_summary,
                time_class_applied,
            ) = self._persist_turn(
                db=db,
                session_obj=session_obj,
                user_text=user_text,
                assistant_text=cleaned_text,
                action_options=action_options,
                battle_summary=battle_summary,
                state_update=state_update,
                query_plan_payload=prepared.query_plan_payload,
                query_plan=prepared.query_plan,
            )
            final_ms = int((time.perf_counter() - stream_start) * 1000)
            rp_option_final_latency_ms.observe(final_ms)

            narrative = self._build_layered_narrative(cleaned_text)

            logger.info(
                "stream_options_ready",
                session_id=str(session_obj.id),
                final_ms=final_ms,
                final_count=len(action_options),
            )

            yield sse_event(
                "done",
                {
                    "turn_id": str(turn.id),
                    "turn_index": turn.turn_index,
                    "usage": turn.token_usage or {},
                    "action_options": action_options,
                    "state_update": state_update,
                    "player_state": player_state,
                    "narrative": narrative,
                    "kernel_delta_summary": kernel_delta_summary,
                    "time_class_applied": time_class_applied,
                    "option_timings": {"final_ms": final_ms},
                },
            )
        except AppError as exc:
            yield sse_event(
                "error",
                {
                    "code": exc.code,
                    "message": exc.message,
                },
            )
        except Exception as exc:  # pragma: no cover
            logger.exception("chat_stream_error", error=str(exc), session_id=str(session_id))
            yield sse_event(
                "error",
                {
                    "code": "stream_internal_error",
                    "message": str(exc),
                },
            )
