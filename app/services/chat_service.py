from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.canon.fact_checker import build_repair_prompt, check_facts, extract_structured_json
from app.core.config import Settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.metrics import (
    rp_provider_latency_seconds,
    rp_retrieval_timeline_hits_total,
    rp_retrieval_vector_hits_total,
    rp_turns_created_total,
)
from app.db.models import AuditLog, Turn, User
from app.db.models import Session as StorySession
from app.memory.compression import compress_retrieval
from app.memory.prompt_assembler import assemble_messages
from app.memory.query_builder import build_query_plan
from app.memory.retriever import retrieve_memory
from app.memory.schemas import EmbeddingProvider, QueryPlan
from app.memory.writer import write_memory
from app.providers.base import LLMProvider
from app.utils.sse import sse_event

logger = get_logger(__name__)


@dataclass
class ChatResult:
    turn_id: str
    turn_index: int
    assistant_text: str
    provider_latency_ms: int
    token_usage: dict[str, int] | None


@dataclass
class PreparedGeneration:
    query_plan: QueryPlan
    query_plan_payload: list[dict[str, str]]
    messages: list[dict[str, str]]
    injection_block: str


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

    def _prepare_generation(
        self,
        *,
        db: Session,
        session_obj: StorySession,
        user_text: str,
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

        t2 = time.perf_counter()
        messages, injection_block = assemble_messages(
            user_text, query_plan, retrieval, recent_turns, self.settings
        )
        self._audit(
            db,
            session_id=session_obj.id,
            turn_id=None,
            action="prompt_assembled",
            payload={"injection": injection_block},
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
        )

    async def _repair_if_needed(
        self,
        *,
        db: Session,
        session_id: uuid.UUID,
        messages: list[dict[str, str]],
        output: str,
    ) -> tuple[str, dict, bool]:
        structured = extract_structured_json(output)
        structured_payload = structured if isinstance(structured, dict) else {}
        facts_used = structured_payload.get("facts_used", []) if isinstance(structured_payload, dict) else []
        fact_result = check_facts(db, session_id=session_id, facts_used=facts_used)
        if fact_result.ok:
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
    ) -> tuple[str, dict, str, list[dict], QueryPlan]:
        prepared = self._prepare_generation(db=db, session_obj=session_obj, user_text=user_text)
        output = await self.provider.generate(prepared.messages, stream=False)
        assert isinstance(output, str)

        final_text, structured, _repaired = await self._repair_if_needed(
            db=db,
            session_id=session_obj.id,
            messages=prepared.messages,
            output=output,
        )
        return (
            final_text,
            structured,
            prepared.injection_block,
            prepared.query_plan_payload,
            prepared.query_plan,
        )

    def _persist_turn(
        self,
        *,
        db: Session,
        session_obj: StorySession,
        user_text: str,
        assistant_text: str,
        query_plan: QueryPlan,
        query_plan_payload: list[dict],
    ) -> Turn:
        turn_index = self._next_turn_index(db, session_obj.id)
        metrics = self.provider.last_metrics

        turn = Turn(
            session_id=session_obj.id,
            turn_index=turn_index,
            user_text=user_text,
            assistant_text=assistant_text,
            provider_latency_ms=metrics.latency_ms if metrics else None,
            token_usage=metrics.token_usage if metrics else None,
        )
        db.add(turn)
        db.flush()

        write_memory(
            db,
            session_id=session_obj.id,
            turn=turn,
            query_plan=query_plan,
            embedding_provider=self.embedding_provider,
        )

        session_obj.updated_at = turn.created_at
        self._audit(
            db,
            session_id=session_obj.id,
            turn_id=turn.id,
            action="turn_committed",
            payload={"turn_index": turn_index, "query_plan": query_plan_payload},
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
        return turn

    async def chat(
        self,
        *,
        db: Session,
        current_user: User,
        session_id: uuid.UUID,
        user_text: str,
    ) -> ChatResult:
        session_obj = self._load_session_or_raise(
            db, session_id=session_id, current_user=current_user
        )
        assistant_text, _structured, _injection, query_plan_payload, query_plan = await self.generate_once(
            db=db, session_obj=session_obj, user_text=user_text
        )
        turn = self._persist_turn(
            db=db,
            session_obj=session_obj,
            user_text=user_text,
            assistant_text=assistant_text,
            query_plan_payload=query_plan_payload,
            query_plan=query_plan,
        )
        metrics = self.provider.last_metrics
        return ChatResult(
            turn_id=str(turn.id),
            turn_index=turn.turn_index,
            assistant_text=assistant_text,
            provider_latency_ms=metrics.latency_ms if metrics else 0,
            token_usage=metrics.token_usage if metrics else None,
        )

    async def chat_stream(
        self,
        *,
        db: Session,
        current_user: User,
        session_id: uuid.UUID,
        user_text: str,
    ) -> AsyncIterator[str]:
        try:
            session_obj = self._load_session_or_raise(
                db, session_id=session_id, current_user=current_user
            )
            prepared = self._prepare_generation(db=db, session_obj=session_obj, user_text=user_text)

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
            final_text, _structured, repaired = await self._repair_if_needed(
                db=db,
                session_id=session_obj.id,
                messages=prepared.messages,
                output=assistant_text,
            )
            if repaired:
                yield sse_event(
                    "delta",
                    {
                        "turn_id": "",
                        "text": "\n\n【系统提示】已根据 Canon 数据修正本轮输出并写入最终版本。",
                    },
                )

            turn = self._persist_turn(
                db=db,
                session_obj=session_obj,
                user_text=user_text,
                assistant_text=final_text,
                query_plan_payload=prepared.query_plan_payload,
                query_plan=prepared.query_plan,
            )

            yield sse_event(
                "done",
                {
                    "turn_id": str(turn.id),
                    "turn_index": turn.turn_index,
                    "usage": turn.token_usage or {},
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
