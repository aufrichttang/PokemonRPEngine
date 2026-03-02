from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_admin_service, require_roles
from app.db.models import User
from app.db.session import get_db
from app.services.admin_service import AdminService

router = APIRouter(prefix="/v1/sessions", tags=["admin"])


class ConfirmRequest(BaseModel):
    event_id: uuid.UUID
    confirm: bool = True
    note: str = ""


@router.get("/{session_id}/memory/debug")
def memory_debug(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
    admin_service: AdminService = Depends(get_admin_service),
    turn_index: int | None = Query(default=None),
) -> dict[str, Any]:
    _ = user
    return admin_service.get_memory_debug(db, session_id=session_id, turn_index=turn_index)


@router.post("/{session_id}/memory/confirm")
def memory_confirm(
    session_id: uuid.UUID,
    payload: ConfirmRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("admin", "operator"))],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> dict:
    _ = user
    return admin_service.confirm_event(
        db,
        session_id=session_id,
        event_id=payload.event_id,
        confirm=payload.confirm,
        note=payload.note,
    )
