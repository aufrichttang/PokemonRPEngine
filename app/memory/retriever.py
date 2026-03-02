from __future__ import annotations

import math
import uuid

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import MemoryChunk, OpenThread, TimelineEvent, Turn
from app.memory.schemas import QueryPlan, RecallItem, RetrievalDebug, RetrievalResult
from app.utils.text import clamp_text


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    length = min(len(a), len(b))
    va = a[:length]
    vb = b[:length]
    dot = sum(x * y for x, y in zip(va, vb, strict=False))
    na = math.sqrt(sum(x * x for x in va))
    nb = math.sqrt(sum(y * y for y in vb))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def retrieve_memory(
    db: Session,
    *,
    session_id: uuid.UUID,
    query_plan: QueryPlan,
    query_embeddings: list[list[float]],
    settings: Settings,
) -> RetrievalResult:
    keywords = [q.q for q in query_plan.queries]

    timeline_stmt: Select[tuple[TimelineEvent]] = (
        select(TimelineEvent)
        .where(TimelineEvent.session_id == session_id, TimelineEvent.canon_level == "confirmed")
        .order_by(desc(TimelineEvent.created_at))
    )
    timeline_rows = db.execute(timeline_stmt).scalars().all()

    filtered = [
        row
        for row in timeline_rows
        if any(
            k
            and (
                k in row.event_text
                or k in (row.location or "")
                or any(k in actor for actor in row.actors)
                or any(k in item for item in row.items)
            )
            for k in keywords
        )
    ]
    if len(filtered) < settings.max_canon_facts:
        filtered.extend([x for x in timeline_rows if x not in filtered])

    canon = [
        {
            "id": str(row.id),
            "event_text": clamp_text(row.event_text, 80),
            "location": row.location or "",
            "canon_level": row.canon_level.value,
        }
        for row in filtered[: settings.max_canon_facts]
    ]

    chunk_rows = (
        db.execute(
            select(MemoryChunk)
            .where(MemoryChunk.session_id == session_id)
            .order_by(desc(MemoryChunk.created_at))
        )
        .scalars()
        .all()
    )

    scored: list[tuple[MemoryChunk, float, int]] = []
    for chunk in chunk_rows:
        score = 0.0
        for q_embed in query_embeddings:
            score = max(score, _cosine(q_embed, list(chunk.embedding)))
        turn_index = (
            db.execute(select(Turn.turn_index).where(Turn.id == chunk.turn_id)).scalar_one_or_none()
            or 0
        )
        scored.append((chunk, score, turn_index))

    scored.sort(key=lambda x: x[1], reverse=True)

    recall_by_chunk: dict[str, RecallItem] = {}
    per_turn_count: dict[int, int] = {}
    for chunk, score, turn_index in scored:
        if score <= 0:
            continue
        key = str(chunk.id)
        if key in recall_by_chunk:
            continue
        cnt = per_turn_count.get(turn_index, 0)
        if cnt >= 2:
            continue
        per_turn_count[turn_index] = cnt + 1
        recall_by_chunk[key] = RecallItem(
            chunk_id=key,
            chunk_text=clamp_text(chunk.chunk_text, 120),
            score=float(round(float(score), 4)),
            turn_index=turn_index,
            importance=float(chunk.importance),
        )
        if len(recall_by_chunk) >= settings.max_recalls:
            break

    thread_rows = (
        db.execute(
            select(OpenThread)
            .where(OpenThread.session_id == session_id, OpenThread.status == "open")
            .order_by(desc(OpenThread.created_at))
            .limit(settings.max_open_threads)
        )
        .scalars()
        .all()
    )

    threads = [
        {
            "id": str(t.id),
            "thread_text": clamp_text(t.thread_text, 60),
            "status": t.status.value,
        }
        for t in thread_rows
    ]

    return RetrievalResult(
        canon_facts=canon,
        recalls=list(recall_by_chunk.values())[: settings.max_recalls],
        open_threads=threads,
        debug=RetrievalDebug(vector_hits=len(recall_by_chunk), timeline_hits=len(canon)),
    )
