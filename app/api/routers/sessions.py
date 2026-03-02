from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session_service
from app.db.models import CanonLevel, User
from app.db.session import get_db
from app.services.session_service import SessionService

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    title: str = "新会话"
    world_template_id: str | None = None
    canon_gen: int = 9
    canon_game: str | None = None
    custom_lore_enabled: bool = False


@router.post("")
def create_session(
    payload: CreateSessionRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> dict:
    sess = session_service.create_session(
        db,
        user_id=user.id,
        title=payload.title,
        world_template_id=payload.world_template_id,
        canon_gen=payload.canon_gen,
        canon_game=payload.canon_game,
        custom_lore_enabled=payload.custom_lore_enabled,
    )
    return {
        "id": str(sess.id),
        "title": sess.title,
        "canon_gen": sess.canon_gen,
        "canon_game": sess.canon_game,
        "custom_lore_enabled": sess.custom_lore_enabled,
    }


@router.get("")
def list_sessions(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> dict:
    sessions = session_service.list_sessions(db, user_id=user.id, page=page, size=size)
    return {
        "items": [
            {
                "id": str(s.id),
                "title": s.title,
                "updated_at": s.updated_at,
                "canon_gen": s.canon_gen,
                "canon_game": s.canon_game,
            }
            for s in sessions
        ]
    }


@router.get("/{session_id}")
def get_session(
    session_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> dict:
    sess = session_service.get_session(db, session_id=session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if sess.user_id != user.id and user.role.value not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Forbidden")

    turns = session_service.get_recent_turns(db, session_id=session_id, limit=30)
    return {
        "id": str(sess.id),
        "title": sess.title,
        "canon_gen": sess.canon_gen,
        "canon_game": sess.canon_game,
        "turns": [
            {
                "id": str(t.id),
                "turn_index": t.turn_index,
                "user_text": t.user_text,
                "assistant_text": t.assistant_text,
                "created_at": t.created_at,
            }
            for t in turns
        ],
    }


@router.delete("/{session_id}")
def delete_session(
    session_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
) -> dict:
    sess = session_service.get_session(db, session_id=session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if sess.user_id != user.id and user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    session_service.delete_session(db, session_id=session_id)
    return {"ok": True}


@router.get("/{session_id}/export")
def export_session(
    session_id: uuid.UUID,
    fmt: str = Query(default="json", pattern="^(json|markdown)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
):
    sess = session_service.get_session(db, session_id=session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if sess.user_id != user.id and user.role.value not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Forbidden")

    exported = session_service.export_session(db, session_id=session_id)
    if fmt == "json":
        return exported

    lines = [
        f"# {exported['session']['title']}",
        "",
        f"- Session ID: {exported['session']['id']}",
        f"- Canon: Gen {exported['session']['canon_gen']} / {exported['session']['canon_game']}",
        "",
    ]
    for t in exported["turns"]:
        lines.extend(
            [
                f"## Turn {t['turn_index']}",
                f"User: {t['user_text']}",
                f"Assistant: {t['assistant_text']}",
                "",
            ]
        )
    return PlainTextResponse("\n".join(lines), media_type="text/markdown")


@router.get("/{session_id}/timeline/events")
def list_timeline_events(
    session_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    session_service: Annotated[SessionService, Depends(get_session_service)],
    canon_level: str | None = Query(default=None, pattern="^(confirmed|implied|pending|conflict)$"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
) -> dict:
    sess = session_service.get_session(db, session_id=session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if sess.user_id != user.id and user.role.value not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Forbidden")

    level_enum = CanonLevel(canon_level) if canon_level else None
    items = session_service.list_timeline_events(
        db,
        session_id=session_id,
        canon_level=level_enum,
        page=page,
        size=size,
    )
    return {
        "items": [
            {
                "id": str(ev.id),
                "turn_id": str(ev.turn_id),
                "canon_level": ev.canon_level.value,
                "event_text": ev.event_text,
                "consequence_text": ev.consequence_text,
                "actors": ev.actors,
                "items": ev.items,
                "location": ev.location,
                "evidence": ev.evidence,
                "created_at": ev.created_at,
            }
            for ev in items
        ]
    }
