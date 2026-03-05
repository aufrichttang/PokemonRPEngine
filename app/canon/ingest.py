from __future__ import annotations

import argparse
import asyncio
import re
from typing import Any

import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import CanonAbility, CanonMove, CanonPokemon, CanonTypeChart
from app.db.session import SessionLocal

POKEAPI_BASE = "https://pokeapi.co/api/v2"
TYPE_NAMES = [
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
GEN_MAP = {
    "generation-i": 1,
    "generation-ii": 2,
    "generation-iii": 3,
    "generation-iv": 4,
    "generation-v": 5,
    "generation-vi": 6,
    "generation-vii": 7,
    "generation-viii": 8,
    "generation-ix": 9,
}


def _has_han(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _has_kana_or_hangul(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff\uac00-\ud7af]", text))


def _unique_names(values: list[str | None]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        if not raw:
            continue
        value = str(raw).strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _pick_name(names: list[dict[str, Any]]) -> str:
    by_lang = {
        str(item.get("language", {}).get("name") or "").lower(): str(item.get("name") or "")
        for item in names
    }
    zh_hans = by_lang.get("zh-hans", "")
    zh_hant = by_lang.get("zh-hant", "")
    en = by_lang.get("en", "")

    if zh_hans and _has_han(zh_hans):
        return zh_hans
    if zh_hant and _has_han(zh_hant):
        return zh_hant
    if zh_hans:
        return zh_hans
    if zh_hant:
        return zh_hant
    if en:
        return en

    for item in names:
        name = str(item.get("name") or "")
        if _has_han(name) and not _has_kana_or_hangul(name):
            return name
    return ""


def _gen_from_api(name: str | None) -> int:
    if not name:
        return 9
    return GEN_MAP.get(name, 9)


async def _fetch_json(
    client: httpx.AsyncClient, url: str, sem: asyncio.Semaphore
) -> dict[str, Any]:
    async with sem:
        res = await client.get(url)
        res.raise_for_status()
        return res.json()


async def fetch_species_rows(limit: int, concurrency: int = 20) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=45) as client:
        res = await client.get(f"{POKEAPI_BASE}/pokemon-species?limit={limit}")
        res.raise_for_status()
        species_list = res.json().get("results", [])

        sem = asyncio.Semaphore(concurrency)
        species_details = await asyncio.gather(
            *[_fetch_json(client, item["url"], sem) for item in species_list]
        )

        pokemon_urls: list[str] = []
        for sp in species_details:
            default_variety = next(
                (v for v in sp.get("varieties", []) if v.get("is_default")),
                sp.get("varieties", [{}])[0],
            )
            pokemon_urls.append(default_variety.get("pokemon", {}).get("url", ""))

        pokemon_details = await asyncio.gather(
            *[_fetch_json(client, u, sem) for u in pokemon_urls if u]
        )

    details_by_name = {p["name"]: p for p in pokemon_details}
    out: list[dict[str, Any]] = []
    for sp in species_details:
        default_variety = next(
            (v for v in sp.get("varieties", []) if v.get("is_default")),
            sp.get("varieties", [{}])[0],
        )
        slug = default_variety.get("pokemon", {}).get("name")
        if not slug:
            continue
        p = details_by_name.get(slug, {})
        stats = {s["stat"]["name"]: int(s["base_stat"]) for s in p.get("stats", [])}
        name_en = next(
            (n["name"] for n in sp.get("names", []) if n.get("language", {}).get("name") == "en"),
            slug,
        )
        name_zh = _pick_name(sp.get("names", [])) or slug
        out.append(
            {
                "dex_no": int(sp.get("id", 0)),
                "slug_id": slug,
                "name_en": name_en,
                "name_zh": name_zh,
                "aliases": _unique_names(
                    [
                        name_zh,
                        name_en,
                        slug,
                        *[str(n.get("name")) for n in sp.get("names", []) if n.get("name")],
                    ]
                ),
                "types": [t["type"]["name"] for t in p.get("types", [])],
                "base_stats": stats,
                "abilities": [a["ability"]["name"] for a in p.get("abilities", [])],
                "height": (p.get("height") or 0) / 10.0 if p.get("height") is not None else None,
                "weight": (p.get("weight") or 0) / 10.0 if p.get("weight") is not None else None,
                "generation": _gen_from_api(sp.get("generation", {}).get("name")),
            }
        )
    out.sort(key=lambda x: x["dex_no"])
    return out


async def fetch_moves(limit: int, concurrency: int = 25) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=45) as client:
        res = await client.get(f"{POKEAPI_BASE}/move?limit={limit}")
        res.raise_for_status()
        rows = res.json().get("results", [])
        sem = asyncio.Semaphore(concurrency)
        details = await asyncio.gather(*[_fetch_json(client, r["url"], sem) for r in rows])

    out: list[dict[str, Any]] = []
    for mv in details:
        name_en = next(
            (n["name"] for n in mv.get("names", []) if n.get("language", {}).get("name") == "en"),
            mv.get("name", ""),
        )
        name_zh = _pick_name(mv.get("names", [])) or name_en
        effect_short = None
        for entry in mv.get("effect_entries", []):
            if entry.get("language", {}).get("name") == "en":
                effect_short = entry.get("short_effect")
                break
        generation = _gen_from_api(mv.get("generation", {}).get("name"))
        out.append(
            {
                "slug_id": mv.get("name", ""),
                "name_en": name_en,
                "name_zh": name_zh,
                "aliases": _unique_names([name_zh, name_en, mv.get("name", "")]),
                "type": mv.get("type", {}).get("name", "normal"),
                "category": mv.get("damage_class", {}).get("name", "status"),
                "power": mv.get("power"),
                "accuracy": mv.get("accuracy"),
                "pp": mv.get("pp"),
                "priority": mv.get("priority") or 0,
                "effect_short": effect_short,
                "generation": generation,
            }
        )
    return out


async def fetch_abilities(limit: int, concurrency: int = 20) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=45) as client:
        res = await client.get(f"{POKEAPI_BASE}/ability?limit={limit}")
        res.raise_for_status()
        rows = res.json().get("results", [])
        sem = asyncio.Semaphore(concurrency)
        details = await asyncio.gather(*[_fetch_json(client, r["url"], sem) for r in rows])

    out: list[dict[str, Any]] = []
    for ab in details:
        name_en = next(
            (n["name"] for n in ab.get("names", []) if n.get("language", {}).get("name") == "en"),
            ab.get("name", ""),
        )
        name_zh = _pick_name(ab.get("names", [])) or name_en
        effect_short = None
        for entry in ab.get("effect_entries", []):
            if entry.get("language", {}).get("name") == "en":
                effect_short = entry.get("short_effect")
                break
        out.append(
            {
                "slug_id": ab.get("name", ""),
                "name_en": name_en,
                "name_zh": name_zh,
                "aliases": _unique_names([name_zh, name_en, ab.get("name", "")]),
                "effect_short": effect_short,
                "generation": _gen_from_api(ab.get("generation", {}).get("name")),
            }
        )
    return out


async def fetch_type_chart(generation: int = 9) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=45) as client:
        res = await client.get(f"{POKEAPI_BASE}/type?limit=50")
        res.raise_for_status()
        rows = res.json().get("results", [])
        type_rows = [r for r in rows if r.get("name") in TYPE_NAMES]
        responses = await asyncio.gather(*[client.get(r["url"]) for r in type_rows])

    matrix: dict[tuple[str, str], float] = {}
    for atk in TYPE_NAMES:
        for defend in TYPE_NAMES:
            matrix[(atk, defend)] = 1.0

    for response in responses:
        response.raise_for_status()
        obj = response.json()
        atk_type = obj.get("name")
        if atk_type not in TYPE_NAMES:
            continue
        rel = obj.get("damage_relations", {})
        for item in rel.get("double_damage_to", []):
            defend = item.get("name")
            if defend in TYPE_NAMES:
                matrix[(atk_type, defend)] = 2.0
        for item in rel.get("half_damage_to", []):
            defend = item.get("name")
            if defend in TYPE_NAMES:
                matrix[(atk_type, defend)] = 0.5
        for item in rel.get("no_damage_to", []):
            defend = item.get("name")
            if defend in TYPE_NAMES:
                matrix[(atk_type, defend)] = 0.0

    return [
        {
            "atk_type": atk,
            "def_type": defend,
            "multiplier": matrix[(atk, defend)],
            "generation": generation,
        }
        for atk in TYPE_NAMES
        for defend in TYPE_NAMES
    ]


def ingest_pokemon(db: Session, rows: list[dict[str, Any]], source_version: str = "pokeapi-v2") -> None:
    db.execute(delete(CanonPokemon))
    for row in rows:
        db.add(
            CanonPokemon(
                dex_no=row["dex_no"],
                slug_id=row["slug_id"],
                name_zh=row["name_zh"],
                name_en=row["name_en"],
                aliases=row["aliases"],
                form=None,
                types=row["types"],
                base_stats=row["base_stats"],
                abilities=row["abilities"],
                height=row["height"],
                weight=row["weight"],
                generation=row["generation"],
                source="pokeapi",
                source_version=source_version,
            )
        )
    db.commit()


def ingest_moves(db: Session, rows: list[dict[str, Any]], source_version: str = "pokeapi-v2") -> None:
    db.execute(delete(CanonMove))
    for row in rows:
        db.add(
            CanonMove(
                slug_id=row["slug_id"],
                name_zh=row["name_zh"],
                name_en=row["name_en"],
                aliases=row["aliases"],
                type=row["type"],
                category=row["category"],
                power=row["power"],
                accuracy=row["accuracy"],
                pp=row["pp"],
                priority=row["priority"],
                effect_short=row["effect_short"],
                generation=row["generation"],
                source="pokeapi",
                source_version=source_version,
            )
        )
    db.commit()


def ingest_abilities(db: Session, rows: list[dict[str, Any]], source_version: str = "pokeapi-v2") -> None:
    db.execute(delete(CanonAbility))
    for row in rows:
        db.add(
            CanonAbility(
                slug_id=row["slug_id"],
                name_zh=row["name_zh"],
                name_en=row["name_en"],
                aliases=row["aliases"],
                effect_short=row["effect_short"],
                generation=row["generation"],
                source="pokeapi",
                source_version=source_version,
            )
        )
    db.commit()


def ingest_type_chart(
    db: Session, rows: list[dict[str, Any]], source_version: str = "pokeapi-v2"
) -> None:
    db.execute(delete(CanonTypeChart))
    for row in rows:
        db.add(
            CanonTypeChart(
                atk_type=row["atk_type"],
                def_type=row["def_type"],
                multiplier=row["multiplier"],
                generation=row["generation"],
                source="pokeapi",
                source_version=source_version,
            )
        )
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Pokemon canon data.")
    parser.add_argument("--pokemon-limit", type=int, default=1025)
    parser.add_argument("--move-limit", type=int, default=1000)
    parser.add_argument("--ability-limit", type=int, default=400)
    parser.add_argument("--generation", type=int, default=9)
    args = parser.parse_args()

    pokemon_rows = asyncio.run(fetch_species_rows(limit=args.pokemon_limit))
    move_rows = asyncio.run(fetch_moves(limit=args.move_limit))
    ability_rows = asyncio.run(fetch_abilities(limit=args.ability_limit))
    chart_rows = asyncio.run(fetch_type_chart(generation=args.generation))

    with SessionLocal() as db:
        ingest_pokemon(db, pokemon_rows)
        ingest_moves(db, move_rows)
        ingest_abilities(db, ability_rows)
        ingest_type_chart(db, chart_rows)

    print(
        f"ingest done: pokemon={len(pokemon_rows)} moves={len(move_rows)} "
        f"abilities={len(ability_rows)} type_chart={len(chart_rows)}"
    )


if __name__ == "__main__":
    main()
