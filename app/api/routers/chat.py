from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import enforce_rate_limit, get_chat_service, get_current_user
from app.db.models import User
from app.db.session import get_db
from app.services.chat_service import ChatService

router = APIRouter(prefix="/v1/sessions", tags=["chat"])


class ChatRequest(BaseModel):
    text: str = Field(min_length=1)
    stream: bool = False
    meta: dict | None = None


@router.post("/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    payload: ChatRequest,
    _rl: Annotated[None, Depends(enforce_rate_limit)],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    _ = payload.meta
    if payload.stream:
        stream = chat_service.chat_stream(
            db=db,
            current_user=user,
            session_id=session_id,
            user_text=payload.text,
        )
        return StreamingResponse(stream, media_type="text/event-stream")

    result = await chat_service.chat(
        db=db,
        current_user=user,
        session_id=session_id,
        user_text=payload.text,
    )
    return {
        "turn_id": result.turn_id,
        "turn_index": result.turn_index,
        "assistant_text": result.assistant_text,
        "provider_latency_ms": result.provider_latency_ms,
        "token_usage": result.token_usage,
    }
