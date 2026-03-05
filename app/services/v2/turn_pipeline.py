from __future__ import annotations

import contextlib
import json
import re
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.battle.fast_resolver import resolve_fast_battle
from app.canon.fact_checker import extract_structured_json, strip_structured_json
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.metrics import (
    rp_option_final_latency_ms,
    rp_provider_narrative_latency_seconds,
    rp_turn_done_seconds,
    rp_turn_first_interactive_seconds,
)
from app.db.models import SaveSlot, SessionTurnV2
from app.db.models import Session as StorySession
from app.memory.budgeter import normalize_pace
from app.services.chat_service import ChatService, PreparedGeneration
from app.services.v2.state_reducer import SlotSnapshot, StateReducer
from app.utils.sse import sse_event

logger = get_logger(__name__)

JSON_MARKER_RE = re.compile(
    r"(<!--\s*json\s*-->|<!--\s*/json\s*-->|```json|```|"
    r"\{\s*\"(?:facts_used|state_update|open_threads_update|action_options)\"|"
    r"\"facts_used\"|\"state_update\"|\"open_threads_update\"|\"action_options\")",
    re.I,
)
HEAD_BLOCK_RE = re.compile(r"<!--\s*head\s*-->\s*(\{[\s\S]*?\})\s*<!--\s*/head\s*-->", re.I)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class TurnPipelineService:
    def __init__(self, *, chat_service: ChatService, state_reducer: StateReducer) -> None:
        self.chat_service = chat_service
        self.state_reducer = state_reducer
        self.settings = chat_service.settings

    async def run_non_stream(
        self,
        db: Session,
        *,
        slot: SaveSlot,
        session_obj: StorySession,
        user_text: str,
        language: str,
        pace: str = "balanced",
        client_turn_id: str | None = None,
    ) -> dict[str, Any]:
        existing = self._load_idempotent_turn(
            db=db,
            slot_id=slot.id,
            client_turn_id=client_turn_id,
        )
        if existing is not None:
            replay = self._done_payload_from_row(existing)
            return {
                "turn_id": replay["turn_id"],
                "turn_index": replay["turn_index"],
                "assistant_text": replay["narrative"]["primary"],
                "narrative": replay["narrative"],
                "action_options": replay["action_options"],
                "battle_summary": replay.get("battle_summary"),
                "state_snapshot": replay.get("state_snapshot") or {},
                "provider_latency_ms": int(replay.get("provider_latency_ms") or 0),
                "token_usage": replay.get("usage") or {},
                "kernel_delta_summary": replay.get("kernel_delta_summary") or {},
                "time_class_applied": replay.get("time_class_applied"),
                "timings": replay.get("timings"),
                "injection_stats": replay.get("injection_stats") or {},
                "pace": replay.get("pace") or normalize_pace(pace),
                "quality_mode": replay.get("quality_mode") or "normal",
            }
        return await self._run_pipeline(
            db=db,
            slot=slot,
            session_obj=session_obj,
            user_text=user_text,
            language=language,
            pace=pace,
            client_turn_id=client_turn_id,
            emit_sse=False,
        )

    async def run_stream(
        self,
        db: Session,
        *,
        slot: SaveSlot,
        session_obj: StorySession,
        user_text: str,
        language: str,
        pace: str = "balanced",
        client_turn_id: str | None = None,
    ) -> AsyncIterator[str]:
        existing = self._load_idempotent_turn(
            db=db,
            slot_id=slot.id,
            client_turn_id=client_turn_id,
        )
        if existing is not None:
            done_payload = self._done_payload_from_row(existing)
            yield sse_event(
                "ack",
                {"slot_id": str(slot.id), "client_turn_id": client_turn_id, "replay": True},
            )
            yield sse_event(
                "primary",
                {"turn_id": str(existing.id), "text": done_payload["narrative"]["primary"]},
            )
            detail_text = str(done_payload["narrative"].get("detail") or "")
            for i in range(0, len(detail_text), 120):
                yield sse_event(
                    "delta",
                    {"turn_id": str(existing.id), "text": detail_text[i : i + 120]},
                )
            yield sse_event("done", done_payload)
            return

        import asyncio

        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def producer() -> None:
            try:
                await self._run_pipeline(
                    db=db,
                    slot=slot,
                    session_obj=session_obj,
                    user_text=user_text,
                    language=language,
                    pace=pace,
                    client_turn_id=client_turn_id,
                    emit_sse=True,
                    emit=lambda event: queue.put_nowait(event),
                )
            except Exception:
                pass
            finally:
                queue.put_nowait(None)

        task = asyncio.create_task(producer())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def _run_pipeline(
        self,
        db: Session,
        *,
        slot: SaveSlot,
        session_obj: StorySession,
        user_text: str,
        language: str,
        pace: str,
        client_turn_id: str | None,
        emit_sse: bool,
        emit: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        language = self.chat_service._normalize_language(language)
        normalized_pace = normalize_pace(pace)

        row = self._begin_pipeline_row(
            db=db,
            slot=slot,
            user_text=user_text,
            client_turn_id=client_turn_id,
        )
        if emit_sse and emit:
            emit(sse_event("ack", {"slot_id": str(slot.id), "client_turn_id": client_turn_id}))

        try:
            prepared = self.chat_service._prepare_generation(
                db=db,
                session_obj=session_obj,
                user_text=user_text,
                language=language,
                pace=normalized_pace,
            )
            quality_mode = prepared.injection_stats.quality_mode
            max_tokens = self._resolve_max_tokens(
                pace=normalized_pace,
                quality_mode=quality_mode,
            )

            messages = self._build_unified_messages(prepared)
            generation_started = time.perf_counter()
            generation = await self.chat_service.provider.generate(
                messages,
                stream=emit_sse,
                json_mode=False,
                max_tokens=max_tokens,
            )

            raw_output = ""
            visible_detail = ""
            primary = ""
            options: list[dict[str, str]] = []
            head_payload: dict[str, Any] = {}
            head_emitted = False
            first_interactive_ms = 0
            first_primary_ms = 0

            if isinstance(generation, str):
                raw_output = generation
                head_payload, body_text = self._extract_head_and_body(raw_output)
                if isinstance(head_payload, dict) and head_payload:
                    primary, options = self._normalize_head_payload(head_payload, user_text=user_text)
                    head_emitted = True
                    visible_detail = self._sanitize_stream_output(body_text)
            else:
                async for chunk in generation:
                    if not chunk:
                        continue
                    raw_output += chunk
                    if not head_emitted:
                        head_payload, body_text = self._extract_head_and_body(raw_output)
                        if isinstance(head_payload, dict) and head_payload:
                            primary, options = self._normalize_head_payload(
                                head_payload,
                                user_text=user_text,
                            )
                            primary, options = self.chat_service._localize_pokemon_names(
                                db=db,
                                session_obj=session_obj,
                                structured_payload=head_payload,
                                user_text=user_text,
                                language=language,
                                assistant_text=primary,
                                action_options=options,
                            )
                            options, options_source = await self._ensure_action_options(
                                user_text=user_text,
                                primary_text=primary,
                                detail_text=body_text,
                                language=language,
                                current_options=options,
                            )
                            logger.info(
                                "action_options_resolved",
                                source=options_source,
                                slot_id=str(slot.id),
                            )
                            primary, primary_source = await self._ensure_primary_narrative(
                                user_text=user_text,
                                primary_text=primary,
                                detail_text=body_text,
                                language=language,
                            )
                            logger.info(
                                "primary_resolved",
                                source=primary_source,
                                slot_id=str(slot.id),
                            )
                            first_interactive_ms = int((time.perf_counter() - started) * 1000)
                            first_primary_ms = first_interactive_ms
                            row.status = "streaming"
                            row.primary_text = primary
                            row.first_interactive_ms = first_interactive_ms
                            row.first_primary_ms = first_primary_ms
                            row.planner_payload = {
                                "head": head_payload,
                                "pace": normalized_pace,
                                "quality_mode": quality_mode,
                                "injection_stats": {
                                    "estimated_tokens": prepared.injection_stats.estimated_tokens,
                                    "sections_used": prepared.injection_stats.sections_used,
                                    "sections_trimmed": prepared.injection_stats.sections_trimmed,
                                },
                            }
                            db.add(row)
                            db.flush()
                            rp_turn_first_interactive_seconds.observe(first_interactive_ms / 1000.0)
                            if emit_sse and emit:
                                emit(
                                    sse_event(
                                        "primary",
                                        {
                                            "turn_id": "",
                                            "text": primary,
                                            "timings": {"first_primary_ms": first_primary_ms},
                                        },
                                    )
                                )
                            head_emitted = True
                            visible_detail = self._sanitize_stream_output(body_text)
                            if emit_sse and emit and visible_detail:
                                emit(sse_event("delta", {"turn_id": "", "text": visible_detail}))
                            continue
                        continue

                    _, body_text = self._extract_head_and_body(raw_output)
                    sanitized = self._sanitize_stream_output(body_text)
                    if len(sanitized) > len(visible_detail):
                        delta = sanitized[len(visible_detail) :]
                        visible_detail = sanitized
                        if emit_sse and emit and delta:
                            emit(sse_event("delta", {"turn_id": "", "text": delta}))

            if not head_emitted:
                recovered_head, recovered_body = self._extract_head_and_body(raw_output)
                if isinstance(recovered_head, dict) and recovered_head:
                    primary, options = self._normalize_head_payload(
                        recovered_head,
                        user_text=user_text,
                    )
                    head_payload = recovered_head
                    visible_detail = self._sanitize_stream_output(recovered_body)
                else:
                    stripped = strip_structured_json(raw_output) or raw_output
                    stripped = self.chat_service._remove_json_leakage(stripped) or stripped
                    layered = self.chat_service._build_layered_narrative(stripped)
                    primary = str(layered.get("primary") or "").strip()
                    options = self.chat_service.action_option_service.extract_action_options(
                        extract_structured_json(raw_output),
                        stripped,
                    )
                    visible_detail = str(layered.get("detail") or stripped)
                    head_payload = {
                        "narrative": {"primary": primary},
                        "action_options": options,
                    }
                primary, options = self.chat_service._localize_pokemon_names(
                    db=db,
                    session_obj=session_obj,
                    structured_payload=head_payload,
                    user_text=user_text,
                    language=language,
                    assistant_text=primary,
                    action_options=options,
                )
                options, options_source = await self._ensure_action_options(
                    user_text=user_text,
                    primary_text=primary,
                    detail_text=visible_detail,
                    language=language,
                    current_options=options,
                )
                logger.info(
                    "action_options_resolved",
                    source=options_source,
                    slot_id=str(slot.id),
                )
                primary, primary_source = await self._ensure_primary_narrative(
                    user_text=user_text,
                    primary_text=primary,
                    detail_text=visible_detail,
                    language=language,
                )
                logger.info(
                    "primary_resolved",
                    source=primary_source,
                    slot_id=str(slot.id),
                )
                first_interactive_ms = int((time.perf_counter() - started) * 1000)
                first_primary_ms = first_interactive_ms
                row.status = "streaming"
                row.primary_text = primary
                row.first_interactive_ms = first_interactive_ms
                row.first_primary_ms = first_primary_ms
                row.planner_payload = {
                    "head": head_payload,
                    "pace": normalized_pace,
                    "quality_mode": quality_mode,
                    "injection_stats": {
                        "estimated_tokens": prepared.injection_stats.estimated_tokens,
                        "sections_used": prepared.injection_stats.sections_used,
                        "sections_trimmed": prepared.injection_stats.sections_trimmed,
                    },
                    "head_recovered": True,
                }
                db.add(row)
                db.flush()
                rp_turn_first_interactive_seconds.observe(first_interactive_ms / 1000.0)
                if emit_sse and emit:
                    emit(
                        sse_event(
                            "primary",
                            {
                                "turn_id": "",
                                "text": primary,
                                "timings": {"first_primary_ms": first_primary_ms},
                            },
                        )
                    )
                    if visible_detail:
                        emit(sse_event("delta", {"turn_id": "", "text": visible_detail}))

            provider_ms = int((time.perf_counter() - generation_started) * 1000)
            provider_name = (
                self.chat_service.provider.last_metrics.provider
                if self.chat_service.provider.last_metrics
                else self.chat_service.settings.llm_provider
            )
            rp_provider_narrative_latency_seconds.labels(provider=provider_name).observe(
                provider_ms / 1000.0
            )

            repaired_text, structured_payload, repaired = await self.chat_service._repair_if_needed(
                db=db,
                session_id=session_obj.id,
                messages=messages,
                output=raw_output,
                allow_model_repair=self._should_run_model_repair(
                    pace=normalized_pace,
                    quality_mode=quality_mode,
                ),
                repair_issue_limit=self.settings.canon_repair_issue_limit,
            )
            text_without_head = self._remove_head_block(repaired_text)
            cleaned_text = strip_structured_json(text_without_head) or text_without_head
            cleaned_text = self.chat_service._remove_json_leakage(cleaned_text) or cleaned_text
            if not cleaned_text:
                cleaned_text = visible_detail or primary

            state_update = self.chat_service._extract_state_update(structured_payload)
            state_update = self.chat_service._normalize_state_update(
                db,
                session_obj=session_obj,
                state_update=state_update,
            )
            cleaned_text, options = self.chat_service._localize_pokemon_names(
                db=db,
                session_obj=session_obj,
                structured_payload=structured_payload,
                user_text=user_text,
                language=language,
                assistant_text=cleaned_text,
                action_options=options,
            )
            options, options_source = await self._ensure_action_options(
                user_text=user_text,
                primary_text=primary,
                detail_text=cleaned_text,
                language=language,
                current_options=options,
            )
            logger.info(
                "action_options_resolved",
                source=options_source,
                slot_id=str(slot.id),
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
                if emit_sse and emit:
                    emit(sse_event("delta", {"turn_id": "", "text": battle_text}))

            if repaired and emit_sse and emit:
                emit(
                    sse_event(
                        "progress",
                        {"stage": "repair", "message": "Canon repair applied."},
                    )
                )

            turn, _player_state, kernel_delta_summary, time_class_applied = (
                self.chat_service._persist_turn(
                    db=db,
                    session_obj=session_obj,
                    user_text=user_text,
                    assistant_text=cleaned_text or primary,
                    action_options=options,
                    battle_summary=battle_summary,
                    state_update=state_update,
                    query_plan_payload=prepared.query_plan_payload,
                    query_plan=prepared.query_plan,
                )
            )

            slot_snapshot = self.state_reducer.sync_slot_from_session(
                db,
                slot=slot,
                session_obj=session_obj,
            )
            done_ms = int((time.perf_counter() - started) * 1000)

            injection_stats_payload = {
                "estimated_tokens": prepared.injection_stats.estimated_tokens,
                "sections_used": prepared.injection_stats.sections_used,
                "sections_trimmed": prepared.injection_stats.sections_trimmed,
            }
            self.state_reducer.upsert_turn_v2(
                db,
                slot=slot,
                turn=turn,
                narrative_primary=primary,
                narrative_detail=cleaned_text if cleaned_text != primary else None,
                state_snapshot=self._snapshot_payload(slot_snapshot),
                client_turn_id=client_turn_id,
                status="done",
                planner_payload={
                    "head": head_payload,
                    "pace": normalized_pace,
                    "quality_mode": quality_mode,
                    "injection_stats": injection_stats_payload,
                },
                first_interactive_ms=first_interactive_ms,
                first_primary_ms=first_primary_ms,
                done_ms=done_ms,
            )
            db.commit()

            rp_option_final_latency_ms.observe(done_ms)
            rp_turn_done_seconds.observe(done_ms / 1000.0)

            narrative_layer = {
                "primary": primary,
                "detail": cleaned_text if cleaned_text != primary else "",
            }
            done_payload = {
                "turn_id": str(turn.id),
                "turn_index": turn.turn_index,
                "narrative": narrative_layer,
                "action_options": options,
                "battle_summary": battle_summary,
                "state_snapshot": self._snapshot_payload(slot_snapshot),
                "usage": turn.token_usage or {},
                "provider_latency_ms": turn.provider_latency_ms or 0,
                "kernel_delta_summary": kernel_delta_summary or {},
                "time_class_applied": time_class_applied,
                "timings": {
                    "first_interactive_ms": first_interactive_ms,
                    "first_primary_ms": first_primary_ms,
                    "done_ms": done_ms,
                    "narrative_ms": provider_ms,
                },
                "injection_stats": injection_stats_payload,
                "pace": normalized_pace,
                "quality_mode": quality_mode,
            }
            if emit_sse and emit:
                emit(sse_event("done", done_payload))

            return {
                "turn_id": str(turn.id),
                "turn_index": turn.turn_index,
                "assistant_text": primary,
                "narrative": narrative_layer,
                "action_options": options,
                "battle_summary": battle_summary,
                "state_snapshot": self._snapshot_payload(slot_snapshot),
                "provider_latency_ms": turn.provider_latency_ms or 0,
                "token_usage": turn.token_usage,
                "kernel_delta_summary": kernel_delta_summary,
                "time_class_applied": time_class_applied,
                "timings": done_payload["timings"],
                "injection_stats": injection_stats_payload,
                "pace": normalized_pace,
                "quality_mode": quality_mode,
            }
        except AppError as exc:
            row.status = "failed"
            db.add(row)
            db.commit()
            if emit_sse and emit:
                emit(sse_event("error", {"code": exc.code, "message": exc.message}))
            raise
        except (httpx.TimeoutException, TimeoutError) as exc:
            row.status = "failed"
            db.add(row)
            db.commit()
            err = AppError(
                code="provider_timeout",
                message="Model response timed out.",
                status_code=504,
                details={"reason": str(exc) or exc.__class__.__name__},
            )
            if emit_sse and emit:
                emit(sse_event("error", {"code": err.code, "message": err.message}))
            raise err from exc
        except Exception as exc:  # pragma: no cover
            logger.exception("turn_pipeline_failed", error=str(exc), slot_id=str(slot.id))
            row.status = "failed"
            db.add(row)
            db.commit()
            err = AppError(
                code="pipeline_failed",
                message="Turn pipeline failed.",
                status_code=500,
                details={"reason": str(exc) or exc.__class__.__name__},
            )
            if emit_sse and emit:
                emit(sse_event("error", {"code": err.code, "message": err.message}))
            raise err from exc

    def _build_unified_messages(self, prepared: PreparedGeneration) -> list[dict[str, str]]:
        directive = (
            "[PIPELINE_STAGE] UNIFIED_TURN\n"
            "必须严格按以下顺序输出：\n"
            "1) 先输出 HEAD 标记块（JSON，仅一段）：\n"
            "<!--HEAD-->{\"narrative\":{\"primary\":\"...\"},"
            "\"action_options\":[{\"id\":\"...\",\"text\":\"...\",\"send_text\":\"...\"}]}<!--/HEAD-->\n"
            "2) 再输出剧情正文（detail，可分段，可流式）。\n"
            "3) 末尾附结构化 JSON（facts_used/state_update/open_threads_update/action_options）。\n"
            "要求：\n"
            "- action_options 必须 3~5 条，且可直接执行；\n"
            "- 全程中文；\n"
            "- HEAD 中 action_options 与末尾 JSON action_options 必须完全一致；\n"
            "- primary 1~2 句，<=120 汉字。"
        )
        messages = list(prepared.messages[:-1])
        messages.append({"role": "system", "content": directive})
        messages.append(prepared.messages[-1])
        return messages

    def _resolve_max_tokens(self, *, pace: str, quality_mode: str) -> int:
        if pace == "fast":
            base = self.settings.llm_narrative_max_tokens_fast
        elif pace == "epic":
            base = self.settings.llm_narrative_max_tokens_epic
        else:
            base = self.settings.llm_narrative_max_tokens_balanced
        if quality_mode == "chapter_climax":
            return max(base, self.settings.llm_narrative_climax_max_tokens)
        return base

    def _should_run_model_repair(self, *, pace: str, quality_mode: str) -> bool:
        mode = (self.settings.canon_repair_mode or "smart").strip().lower()
        if mode == "off":
            return False
        if mode == "full":
            return True
        # smart: only run expensive second pass for high-value turns
        return pace == "epic" or quality_mode == "chapter_climax"

    def _extract_head_and_body(self, text: str) -> tuple[dict[str, Any] | None, str]:
        match = HEAD_BLOCK_RE.search(text or "")
        if not match:
            return None, text or ""
        raw = match.group(1).strip()
        try:
            parsed = json.loads(raw)
        except Exception:
            return None, text
        if not isinstance(parsed, dict):
            return None, text
        body = f"{text[:match.start()]}{text[match.end():]}"
        return parsed, body

    def _remove_head_block(self, text: str) -> str:
        return HEAD_BLOCK_RE.sub("", text or "").strip()

    def _normalize_head_payload(
        self,
        payload: dict[str, Any],
        *,
        user_text: str,
    ) -> tuple[str, list[dict[str, str]]]:
        primary = str(_as_dict(payload.get("narrative")).get("primary") or "").strip()
        if not primary:
            primary = str(payload.get("primary") or "").strip()
        options = self.chat_service.action_option_service.extract_action_options(payload, primary or user_text)
        return primary, options

    async def _ensure_action_options(
        self,
        *,
        user_text: str,
        primary_text: str,
        detail_text: str,
        language: str,
        current_options: list[dict[str, str]],
    ) -> tuple[list[dict[str, str]], str]:
        if current_options:
            return current_options, "head"

        from_text = self.chat_service.action_option_service.extract_action_options(
            {},
            f"{primary_text}\n{detail_text}",
        )
        if from_text:
            return from_text, "text_extract"

        repaired = await self._repair_options_with_llm(
            user_text=user_text,
            primary_text=primary_text,
            detail_text=detail_text,
            language=language,
        )
        if repaired:
            return repaired, "llm_repair"

        fallback = self.chat_service.action_option_service.build_dynamic_fallback_options(
            user_text=user_text,
            primary_text=primary_text or detail_text,
        )
        return fallback, "dynamic_fallback"

    async def _repair_options_with_llm(
        self,
        *,
        user_text: str,
        primary_text: str,
        detail_text: str,
        language: str,
    ) -> list[dict[str, str]]:
        prompt = (
            "请根据以下剧情生成 3~5 条可点击动作选项，仅输出 JSON：\n"
            '{"action_options":[{"id":"...","text":"...","send_text":"..."}]}\n'
            "要求：中文、简洁、可直接执行，send_text 与 text 语义一致。\n\n"
            f"用户输入：{user_text}\n"
            f"主叙事：{primary_text}\n"
            f"补充叙事：{detail_text[:800]}\n"
        )
        messages = [
            {
                "role": "system",
                "content": "你是动作规划器，只返回 JSON，不要任何解释。",
            },
            {"role": "user", "content": prompt},
        ]
        try:
            generated = await self.chat_service.provider.generate(
                messages,
                stream=False,
                json_mode=True,
                max_tokens=220,
                language=language,
            )
            text = str(generated or "").strip()
            if not text:
                return []

            payload: dict[str, Any] | None = None
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                payload = extract_structured_json(text)

            if not isinstance(payload, dict):
                return []
            return self.chat_service.action_option_service.extract_action_options(payload, "")
        except Exception as exc:  # pragma: no cover - network/provider variance
            logger.warning("repair_action_options_failed", reason=str(exc))
            return []

    async def _ensure_primary_narrative(
        self,
        *,
        user_text: str,
        primary_text: str,
        detail_text: str,
        language: str,
    ) -> tuple[str, str]:
        current = (primary_text or "").strip()
        if current:
            return current, "head"

        from_detail = self._derive_primary_from_text(detail_text)
        if from_detail:
            return from_detail, "detail_extract"

        repaired = await self._repair_primary_with_llm(
            user_text=user_text,
            detail_text=detail_text,
            language=language,
        )
        if repaired:
            return repaired, "llm_repair"

        fallback = "剧情继续推进：你的行动正在引发新的变化。"
        return fallback, "dynamic_fallback"

    async def _repair_primary_with_llm(
        self,
        *,
        user_text: str,
        detail_text: str,
        language: str,
    ) -> str:
        prompt = (
            "请根据以下上下文，输出 1~2 句中文主叙事（<=120 字）。"
            "仅返回 JSON：{\"primary\":\"...\"}\n"
            f"用户输入：{user_text}\n"
            f"细节文本：{detail_text[:900]}"
        )
        messages = [
            {"role": "system", "content": "你是剧情压缩器，只返回 JSON，不要解释。"},
            {"role": "user", "content": prompt},
        ]
        try:
            generated = await self.chat_service.provider.generate(
                messages,
                stream=False,
                json_mode=True,
                max_tokens=120,
                language=language,
            )
            text = str(generated or "").strip()
            if not text:
                return ""
            payload: dict[str, Any] | None = None
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                payload = extract_structured_json(text)

            if not isinstance(payload, dict):
                return ""
            primary = str(payload.get("primary") or "").strip()
            return self._derive_primary_from_text(primary)
        except Exception as exc:  # pragma: no cover
            logger.warning("repair_primary_failed", reason=str(exc))
            return ""

    def _derive_primary_from_text(self, text: str) -> str:
        cleaned = self._sanitize_stream_output(text or "")
        cleaned = strip_structured_json(cleaned) or cleaned
        cleaned = self.chat_service._remove_json_leakage(cleaned) or cleaned
        cleaned = cleaned.strip()
        if not cleaned:
            return ""

        for line in cleaned.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("{") or line.startswith("```") or line.startswith("<!--"):
                continue
            if any(k in line for k in ("facts_used", "state_update", "open_threads_update")):
                continue
            if len(line) <= 120:
                return line
            return line[:120].rstrip("，,、；;。.!?！？") + "。"
        return ""

    def _load_idempotent_turn(
        self,
        *,
        db: Session,
        slot_id: uuid.UUID,
        client_turn_id: str | None,
    ) -> SessionTurnV2 | None:
        if not client_turn_id:
            return None
        return db.execute(
            select(SessionTurnV2).where(
                SessionTurnV2.slot_id == slot_id,
                SessionTurnV2.client_turn_id == client_turn_id,
                SessionTurnV2.status == "done",
            )
        ).scalar_one_or_none()

    def _begin_pipeline_row(
        self,
        *,
        db: Session,
        slot: SaveSlot,
        user_text: str,
        client_turn_id: str | None,
    ) -> SessionTurnV2:
        if client_turn_id:
            in_flight = db.execute(
                select(SessionTurnV2).where(
                    SessionTurnV2.slot_id == slot.id,
                    SessionTurnV2.client_turn_id == client_turn_id,
                )
            ).scalar_one_or_none()
            if in_flight is not None:
                raise AppError(
                    code="duplicate_client_turn",
                    message="Duplicate client turn request is already processed.",
                    status_code=409,
                )
        turn_index = self.chat_service._next_turn_index(db, slot.session_id)
        row = SessionTurnV2(
            slot_id=slot.id,
            client_turn_id=client_turn_id,
            status="planning",
            turn_index=turn_index,
            user_text=user_text,
            assistant_text="",
            action_options=[],
            state_snapshot={},
        )
        db.add(row)
        db.flush()
        return row

    def _sanitize_stream_output(self, text: str) -> str:
        stripped = text or ""
        marker = JSON_MARKER_RE.search(stripped)
        if marker:
            stripped = stripped[: marker.start()]
        return stripped.rstrip()

    def _snapshot_payload(self, snapshot: SlotSnapshot) -> dict[str, Any]:
        return {
            "story_progress": snapshot.story_progress,
            "team": snapshot.player_state.get("team", []),
            "storage_box": snapshot.player_state.get("storage_box", []),
            "inventory": snapshot.player_state.get("inventory", {}),
            "kernel_summary": snapshot.player_state.get("kernel_summary", {}),
        }

    def _done_payload_from_row(self, row: SessionTurnV2) -> dict[str, Any]:
        narrative = {
            "primary": row.primary_text or row.narrative_primary or row.assistant_text,
            "detail": row.detail_text or row.narrative_detail or "",
        }
        if not narrative["detail"] and narrative["primary"] != row.assistant_text:
            narrative["detail"] = row.assistant_text

        planner_payload = _as_dict(row.planner_payload)
        injection_stats = _as_dict(planner_payload.get("injection_stats"))
        pace = str(planner_payload.get("pace") or "balanced")
        quality_mode = str(planner_payload.get("quality_mode") or "normal")

        return {
            "turn_id": str(row.id),
            "turn_index": row.turn_index,
            "narrative": narrative,
            "action_options": row.action_options or [],
            "battle_summary": row.battle_summary or {},
            "state_snapshot": row.state_snapshot or {},
            "usage": row.token_usage or {},
            "provider_latency_ms": row.provider_latency_ms or 0,
            "kernel_delta_summary": _as_dict(_as_dict(row.state_snapshot).get("kernel_summary")),
            "time_class_applied": None,
            "timings": {
                "first_interactive_ms": row.first_interactive_ms or 0,
                "first_primary_ms": row.first_primary_ms or 0,
                "done_ms": row.done_ms or 0,
            },
            "injection_stats": injection_stats,
            "pace": pace,
            "quality_mode": quality_mode,
        }
