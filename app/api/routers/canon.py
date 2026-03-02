from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import CanonMove, CanonPokemon, CanonTypeChart, User
from app.db.session import get_db

router = APIRouter(prefix="/v1/canon", tags=["canon"])


@router.get("/pokemon")
def list_canon_pokemon(
    q: str | None = Query(default=None),
    generation: int | None = Query(default=None, ge=1, le=9),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = (
        select(CanonPokemon)
        .order_by(CanonPokemon.dex_no.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    if generation:
        stmt = stmt.where(CanonPokemon.generation == generation)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                CanonPokemon.slug_id.ilike(like),
                CanonPokemon.name_zh.ilike(like),
                CanonPokemon.name_en.ilike(like),
                cast(CanonPokemon.aliases, String).ilike(like),
            )
        )
    rows = list(db.execute(stmt).scalars().all())
    return {
        "items": [
            {
                "id": str(p.id),
                "dex_no": p.dex_no,
                "slug_id": p.slug_id,
                "name_zh": p.name_zh,
                "name_en": p.name_en,
                "aliases": p.aliases,
                "types": p.types,
                "generation": p.generation,
            }
            for p in rows
        ]
    }


@router.get("/moves")
def list_canon_moves(
    q: str | None = Query(default=None),
    generation: int | None = Query(default=None, ge=1, le=9),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(CanonMove).order_by(CanonMove.name_zh.asc()).offset((page - 1) * size).limit(size)
    if generation:
        stmt = stmt.where(CanonMove.generation == generation)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                CanonMove.slug_id.ilike(like),
                CanonMove.name_zh.ilike(like),
                CanonMove.name_en.ilike(like),
                cast(CanonMove.aliases, String).ilike(like),
            )
        )
    rows = list(db.execute(stmt).scalars().all())
    return {
        "items": [
            {
                "id": str(m.id),
                "slug_id": m.slug_id,
                "name_zh": m.name_zh,
                "name_en": m.name_en,
                "aliases": m.aliases,
                "type": m.type,
                "category": m.category,
                "power": m.power,
                "accuracy": m.accuracy,
                "pp": m.pp,
                "priority": m.priority,
                "generation": m.generation,
            }
            for m in rows
        ]
    }


@router.get("/type-chart")
def get_type_chart(
    generation: int = Query(default=9, ge=1, le=9),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rows = list(
        db.execute(
            select(CanonTypeChart)
            .where(CanonTypeChart.generation == generation)
            .order_by(CanonTypeChart.atk_type.asc(), CanonTypeChart.def_type.asc())
        )
        .scalars()
        .all()
    )
    matrix: dict[str, dict[str, float]] = {}
    for row in rows:
        matrix.setdefault(row.atk_type, {})[row.def_type] = row.multiplier
    return {
        "generation": generation,
        "items": [
            {"atk_type": r.atk_type, "def_type": r.def_type, "multiplier": r.multiplier}
            for r in rows
        ],
        "matrix": matrix,
    }
