from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import enforce_rate_limit, get_current_user, get_game_facade_service
from app.db.models import User
from app.db.session import get_db
from app.services.v2.game_facade import GameFacadeService

router = APIRouter(prefix="/v2/game", tags=["game-v2"])


class CreateSlotRequest(BaseModel):
    slot_name: str = Field(default="新冒险", min_length=1, max_length=120)
    world_seed: str | None = Field(default=None, max_length=64)
    canon_gen: int = Field(default=9, ge=1, le=9)
    canon_game: str | None = Field(default=None, max_length=120)
    player_profile: dict[str, Any] | None = None


class TurnRequest(BaseModel):
    text: str = Field(min_length=1)
    stream: bool = False
    language: str = "zh"
    pace: str = Field(default="balanced", pattern="^(fast|balanced|epic)$")
    client_turn_id: str | None = Field(default=None, max_length=64)


class ActionRequest(BaseModel):
    stream: bool = True
    language: str = "zh"
    pace: str = Field(default="balanced", pattern="^(fast|balanced|epic)$")
    client_turn_id: str | None = Field(default=None, max_length=64)


@router.post("/slots")
def create_slot(
    payload: CreateSlotRequest,
    _rl: Annotated[None, Depends(enforce_rate_limit)],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    game: Annotated[GameFacadeService, Depends(get_game_facade_service)],
) -> dict[str, Any]:
    return game.create_slot(
        db,
        current_user=user,
        slot_name=payload.slot_name,
        world_seed=payload.world_seed,
        canon_gen=payload.canon_gen,
        canon_game=payload.canon_game,
        player_profile=payload.player_profile,
    )


@router.get("/slots")
def list_slots(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    game: GameFacadeService = Depends(get_game_facade_service),
) -> dict[str, Any]:
    return game.list_slots(db, current_user=user, page=page, size=size)


@router.get("/slots/{slot_id}")
def get_slot(
    slot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    game: GameFacadeService = Depends(get_game_facade_service),
) -> dict[str, Any]:
    return game.get_slot(db, slot_id=slot_id, current_user=user)


@router.get("/slots/{slot_id}/lore")
def get_lore(
    slot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    game: GameFacadeService = Depends(get_game_facade_service),
) -> dict[str, Any]:
    return game.get_lore(db, slot_id=slot_id, current_user=user)


@router.get("/slots/{slot_id}/time")
def get_time(
    slot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    game: GameFacadeService = Depends(get_game_facade_service),
) -> dict[str, Any]:
    return game.get_time(db, slot_id=slot_id, current_user=user)


@router.get("/slots/{slot_id}/factions")
def get_factions(
    slot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    game: GameFacadeService = Depends(get_game_facade_service),
) -> dict[str, Any]:
    return game.get_factions(db, slot_id=slot_id, current_user=user)


@router.post("/slots/{slot_id}/debug/reclassify-memories")
def reclassify_memories(
    slot_id: uuid.UUID,
    _rl: Annotated[None, Depends(enforce_rate_limit)],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    game: Annotated[GameFacadeService, Depends(get_game_facade_service)],
) -> dict[str, Any]:
    return game.reclassify_memories(db, slot_id=slot_id, current_user=user)


@router.post("/slots/{slot_id}/turns")
async def create_turn(
    slot_id: uuid.UUID,
    payload: TurnRequest,
    _rl: Annotated[None, Depends(enforce_rate_limit)],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    game: Annotated[GameFacadeService, Depends(get_game_facade_service)],
):
    if payload.stream:
        stream = game.turn_stream(
            db,
            slot_id=slot_id,
            current_user=user,
            text=payload.text,
            language=payload.language,
            pace=payload.pace,
            client_turn_id=payload.client_turn_id,
        )
        return StreamingResponse(stream, media_type="text/event-stream")
    return await game.turn(
        db,
        slot_id=slot_id,
        current_user=user,
        text=payload.text,
        language=payload.language,
        pace=payload.pace,
        client_turn_id=payload.client_turn_id,
    )


@router.post("/slots/{slot_id}/actions/{action_id}")
async def execute_action(
    slot_id: uuid.UUID,
    action_id: str,
    payload: ActionRequest,
    _rl: Annotated[None, Depends(enforce_rate_limit)],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    game: Annotated[GameFacadeService, Depends(get_game_facade_service)],
):
    result = await game.execute_action(
        db,
        slot_id=slot_id,
        current_user=user,
        action_id=action_id,
        stream=payload.stream,
        language=payload.language,
        pace=payload.pace,
        client_turn_id=payload.client_turn_id,
    )
    if payload.stream:
        return StreamingResponse(result, media_type="text/event-stream")
    return result


@router.get("/slots/{slot_id}/export")
def export_slot(
    slot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    game: GameFacadeService = Depends(get_game_facade_service),
) -> PlainTextResponse:
    text = game.dump_slot(db, slot_id=slot_id, current_user=user)
    return PlainTextResponse(text, media_type="application/json")
