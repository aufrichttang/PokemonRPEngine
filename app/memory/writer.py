from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.metrics import rp_conflicts_total
from app.db.models import AuditLog, MemoryChunk, OpenThread, TimelineEvent, Turn
from app.kernels.event_classifier import classify_event_metadata
from app.memory.schemas import EmbeddingProvider, QueryPlan
from app.utils.text import split_sentences

EVENT_VERBS = [
    "获得",
    "失去",
    "答应",
    "见到",
    "到达",
    "离开",
    "告诉",
    "发现",
    "决定",
    "捕获",
    "击败",
]
NEGATIONS = ["从未", "没有", "不是", "并未", "不曾"]


@dataclass
class WriteResult:
    event_ids: list[str]
    chunk_ids: list[str]
    conflicts: int
    time_classes: list[str]


def _clean_assistant_text(text: str) -> str:
    return re.sub(r"<!--JSON-->.*?<!--/JSON-->", "", text, flags=re.DOTALL).strip()


def _extract_event_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for sent in split_sentences(text):
        if any(v in sent for v in EVENT_VERBS):
            candidates.append(sent)
    return candidates


def _classify_canon_level(sent: str) -> str:
    if any(token in sent for token in ["确认", "已经", "成功", "最终", "确实", "达成"]):
        return "confirmed"
    if any(token in sent for token in ["可能", "似乎", "也许", "传闻", "怀疑"]):
        return "pending"
    return "implied"


def _is_conflict(existing: str, candidate: str) -> bool:
    existing_neg = any(n in existing for n in NEGATIONS)
    candidate_neg = any(n in candidate for n in NEGATIONS)
    if existing_neg == candidate_neg:
        return False

    def grams(text: str) -> set[str]:
        normalized = re.sub(r"[\W_]+", "", text)
        for token in NEGATIONS:
            normalized = normalized.replace(token, "")
        output: set[str] = set()
        for i in range(len(normalized) - 1):
            output.add(normalized[i : i + 2])
        for i in range(len(normalized) - 2):
            output.add(normalized[i : i + 3])
        return output

    overlap = grams(existing) & grams(candidate)
    return len(overlap) >= 2


def write_memory(
    db: Session,
    *,
    session_id: uuid.UUID,
    turn: Turn,
    query_plan: QueryPlan,
    embedding_provider: EmbeddingProvider,
) -> WriteResult:
    text = _clean_assistant_text(turn.assistant_text)
    candidates = _extract_event_candidates(text)

    existing_confirmed = (
        db.execute(
            select(TimelineEvent)
            .where(TimelineEvent.session_id == session_id, TimelineEvent.canon_level == "confirmed")
            .order_by(desc(TimelineEvent.created_at))
        )
        .scalars()
        .all()
    )

    event_ids: list[str] = []
    conflict_count = 0
    time_classes: set[str] = set()

    for sent in candidates:
        level = _classify_canon_level(sent)
        metadata = classify_event_metadata(text=sent, canon_level=level, actors=[])
        conflict_event = None
        for ex in existing_confirmed:
            if _is_conflict(ex.event_text, sent):
                conflict_event = ex
                break

        if conflict_event:
            conflict_count += 1
            rp_conflicts_total.inc()
            event = TimelineEvent(
                session_id=session_id,
                turn_id=turn.id,
                event_text=f"冲突: {sent}",
                canon_level="conflict",
                time_class=metadata["time_class"],
                source_trust=metadata["source_trust"],
                witness_count=metadata["witness_count"],
                narrative_conflict_score=metadata["narrative_conflict_score"],
                canon_legacy_tags=metadata["canon_legacy_tags"],
                actors=[],
                items=[],
                evidence={"turn_index": turn.turn_index, "snippet": sent},
            )
            db.add(event)
            db.flush()
            db.add(
                OpenThread(
                    session_id=session_id,
                    thread_text=f"解释冲突：{sent}",
                    related_entities={"related_event_id": str(conflict_event.id)},
                )
            )
            db.add(
                AuditLog(
                    session_id=session_id,
                    turn_id=turn.id,
                    action="conflict_detected",
                    payload={"event": sent, "conflict_with": str(conflict_event.id)},
                )
            )
            event_ids.append(str(event.id))
            time_classes.add(str(metadata["time_class"]))
            continue

        event = TimelineEvent(
            session_id=session_id,
            turn_id=turn.id,
            event_text=sent,
            canon_level=level,
            time_class=metadata["time_class"],
            source_trust=metadata["source_trust"],
            witness_count=metadata["witness_count"],
            narrative_conflict_score=metadata["narrative_conflict_score"],
            canon_legacy_tags=metadata["canon_legacy_tags"],
            actors=[],
            items=[],
            evidence={"turn_index": turn.turn_index, "snippet": sent},
        )
        db.add(event)
        db.flush()
        event_ids.append(str(event.id))
        time_classes.add(str(metadata["time_class"]))

    chunks = [c.strip() for c in re.split(r"\n{2,}", text) if c.strip()]
    if not chunks:
        chunks = [text]

    chunk_ids: list[str] = []
    vectors = embedding_provider.embed(chunks)
    actors = [q.q for q in query_plan.queries if q.type.value == "actors"]
    locations = [q.q for q in query_plan.queries if q.type.value == "locations"]
    items = [q.q for q in query_plan.queries if q.type.value == "items"]

    for idx, chunk in enumerate(chunks):
        importance = 0.8 if any(k in chunk for k in ["承诺", "线索", "秘密"]) else 0.5
        chunk_meta = classify_event_metadata(text=chunk, canon_level="implied", actors=actors)
        item = MemoryChunk(
            session_id=session_id,
            turn_id=turn.id,
            chunk_text=chunk[:300],
            tags={"actors": actors, "locations": locations, "items": items, "topics": []},
            importance=importance,
            time_class=chunk_meta["time_class"],
            source_trust=chunk_meta["source_trust"],
            witness_count=chunk_meta["witness_count"],
            narrative_conflict_score=chunk_meta["narrative_conflict_score"],
            canon_legacy_tags=chunk_meta["canon_legacy_tags"],
            embedding=vectors[idx],
        )
        db.add(item)
        db.flush()
        chunk_ids.append(str(item.id))

    db.add(
        AuditLog(
            session_id=session_id,
            turn_id=turn.id,
            action="timeline_write",
            payload={
                "event_ids": event_ids,
                "conflicts": conflict_count,
                "time_classes": sorted(time_classes),
            },
        )
    )
    db.add(
        AuditLog(
            session_id=session_id,
            turn_id=turn.id,
            action="vector_write",
            payload={"chunk_ids": chunk_ids},
        )
    )

    return WriteResult(
        event_ids=event_ids,
        chunk_ids=chunk_ids,
        conflicts=conflict_count,
        time_classes=sorted(time_classes),
    )
