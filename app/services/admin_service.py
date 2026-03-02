from __future__ import annotations

import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import AuditLog, TimelineEvent


class AdminService:
    def get_memory_debug(
        self,
        db: Session,
        *,
        session_id: uuid.UUID,
        turn_index: int | None,
    ) -> dict:
        _ = turn_index
        logs = (
            db.execute(
                select(AuditLog)
                .where(
                    AuditLog.session_id == session_id,
                    AuditLog.action.in_(["query_builder", "retrieval", "prompt_assembled"]),
                )
                .order_by(desc(AuditLog.created_at))
                .limit(20)
            )
            .scalars()
            .all()
        )

        payload: dict[str, dict] = {}
        for log in logs:
            payload[log.action] = log.payload

        return {
            "query_plan": payload.get("query_builder", {}).get("queries", []),
            "retrieval": payload.get("retrieval", {}),
            "prompt_injection": payload.get("prompt_assembled", {}).get("injection", ""),
        }

    def confirm_event(
        self,
        db: Session,
        *,
        session_id: uuid.UUID,
        event_id: uuid.UUID,
        confirm: bool,
        note: str,
    ) -> dict:
        event = db.execute(
            select(TimelineEvent).where(
                TimelineEvent.id == event_id,
                TimelineEvent.session_id == session_id,
            )
        ).scalar_one_or_none()
        if not event:
            raise AppError(
                code="event_not_found", message="Timeline event not found", status_code=404
            )

        if confirm:
            event.canon_level = "confirmed"
        db.add(event)
        db.add(
            AuditLog(
                session_id=session_id,
                turn_id=event.turn_id,
                action="memory_confirm",
                payload={"event_id": str(event.id), "confirm": confirm, "note": note},
            )
        )
        db.commit()
        db.refresh(event)
        return {"event_id": str(event.id), "canon_level": event.canon_level.value}
