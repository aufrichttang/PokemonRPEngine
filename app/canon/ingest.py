from __future__ import annotations

import argparse
import asyncio
from typing import Any

import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import CanonMove, CanonPokemon
from app.db.session import SessionLocal


async def fetch_pokemon(limit: int = 151) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(f"https://pokeapi.co/api/v2/pokemon?limit={limit}")
        res.raise_for_status()
        return res.json().get("results", [])


def ingest(db: Session, rows: list[dict[str, Any]], source_version: str = "pokeapi-v2") -> None:
    db.execute(delete(CanonPokemon))
    for idx, row in enumerate(rows, 1):
        slug = row["name"]
        db.add(
            CanonPokemon(
                dex_no=idx,
                slug_id=slug,
                name_zh=slug,
                name_en=slug,
                aliases=[slug],
                form=None,
                types=["unknown"],
                base_stats={},
                abilities=[],
                generation=9,
                source="pokeapi",
                source_version=source_version,
            )
        )
    db.commit()


def ingest_stub_moves(db: Session, source_version: str = "manual-seed") -> None:
    db.execute(delete(CanonMove))
    db.add(
        CanonMove(
            slug_id="shadow-ball",
            name_zh="暗影球",
            name_en="Shadow Ball",
            aliases=["暗影球", "shadow ball"],
            type="ghost",
            category="special",
            power=80,
            accuracy=100,
            pp=15,
            priority=0,
            effect_short="May lower Sp. Def",
            generation=9,
            source="seed",
            source_version=source_version,
        )
    )
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Pokemon canon data.")
    parser.add_argument("--limit", type=int, default=151)
    args = parser.parse_args()

    rows = asyncio.run(fetch_pokemon(limit=args.limit))
    with SessionLocal() as db:
        ingest(db, rows)
        ingest_stub_moves(db)


if __name__ == "__main__":
    main()
