from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import CanonMove, CanonPokemon, CanonTypeChart

TYPES = [
    "normal",
    "fire",
    "water",
    "electric",
    "grass",
    "ice",
    "fighting",
    "poison",
    "ground",
    "flying",
    "psychic",
    "bug",
    "rock",
    "ghost",
    "dragon",
    "dark",
    "steel",
    "fairy",
]


@dataclass
class ValidationReport:
    ok: bool
    errors: list[str]


def validate_canon_integrity(db: Session) -> ValidationReport:
    errors: list[str] = []

    dup_dex = db.execute(
        select(CanonPokemon.dex_no, func.count(CanonPokemon.id))
        .group_by(CanonPokemon.dex_no)
        .having(func.count(CanonPokemon.id) > 1)
    ).all()
    if dup_dex:
        errors.append(f"duplicate dex entries: {dup_dex}")

    move_missing = db.execute(
        select(func.count(CanonMove.id)).where(CanonMove.type.is_(None))
    ).scalar_one()
    if move_missing:
        errors.append(f"moves missing type: {move_missing}")

    matrix_count = db.execute(select(func.count(CanonTypeChart.id))).scalar_one()
    if matrix_count < 18 * 18:
        errors.append(f"type chart incomplete: got={matrix_count}, expected>={18*18}")

    return ValidationReport(ok=not errors, errors=errors)
