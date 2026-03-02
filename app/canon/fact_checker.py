from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CanonAbility, CanonMove, CanonPokemon, CanonTypeChart
from app.db.models import Session as StorySession

JSON_BLOCK_PATTERN = re.compile(r"<!--JSON-->(.*?)<!--/JSON-->", re.DOTALL)


@dataclass
class FactIssue:
    code: str
    message: str
    fact: dict[str, Any]


@dataclass
class FactCheckResult:
    ok: bool
    issues: list[FactIssue]


def extract_structured_json(text: str) -> dict[str, Any]:
    match = JSON_BLOCK_PATTERN.search(text)
    if not match:
        return {"facts_used": [], "state_update": {}, "open_threads_update": []}
    payload = match.group(1).strip()
    try:
        obj = json.loads(payload)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    return {"facts_used": [], "state_update": {}, "open_threads_update": []}


def _exists_by_slug_or_alias(row_slug: str, aliases: list[str], value: str) -> bool:
    v = value.lower()
    if row_slug.lower() == v:
        return True
    return any(a.lower() == v for a in aliases)


def check_facts(
    db: Session,
    *,
    session_id: uuid.UUID,
    facts_used: list[dict[str, Any]],
) -> FactCheckResult:
    session_obj = db.execute(select(StorySession).where(StorySession.id == session_id)).scalar_one()
    canon_gen = session_obj.canon_gen

    issues: list[FactIssue] = []

    for fact in facts_used:
        kind = fact.get("kind")
        slug = str(fact.get("slug") or fact.get("id") or "").strip()
        if not slug:
            issues.append(FactIssue(code="missing_slug", message="fact slug missing", fact=fact))
            continue

        if kind == "pokemon":
            rows = db.execute(
                select(CanonPokemon).where(CanonPokemon.generation <= canon_gen)
            ).scalars()
            if not any(_exists_by_slug_or_alias(r.slug_id, r.aliases, slug) for r in rows):
                issues.append(
                    FactIssue(code="pokemon_not_found", message=f"{slug} not found", fact=fact)
                )
        elif kind == "move":
            rows = db.execute(select(CanonMove).where(CanonMove.generation <= canon_gen)).scalars()
            if not any(_exists_by_slug_or_alias(r.slug_id, r.aliases, slug) for r in rows):
                issues.append(
                    FactIssue(code="move_not_found", message=f"{slug} not found", fact=fact)
                )
        elif kind == "ability":
            rows = db.execute(
                select(CanonAbility).where(CanonAbility.generation <= canon_gen)
            ).scalars()
            if not any(_exists_by_slug_or_alias(r.slug_id, r.aliases, slug) for r in rows):
                issues.append(
                    FactIssue(code="ability_not_found", message=f"{slug} not found", fact=fact)
                )
        elif kind == "type_chart":
            atk = fact.get("atk_type")
            defend = fact.get("def_type")
            if not atk or not defend:
                issues.append(
                    FactIssue(
                        code="type_chart_missing_fields", message="atk/def missing", fact=fact
                    )
                )
                continue
            found = db.execute(
                select(CanonTypeChart).where(
                    CanonTypeChart.atk_type == atk,
                    CanonTypeChart.def_type == defend,
                    CanonTypeChart.generation <= canon_gen,
                )
            ).scalar_one_or_none()
            if not found:
                issues.append(
                    FactIssue(
                        code="type_chart_not_found", message="type relation not found", fact=fact
                    )
                )

    return FactCheckResult(ok=not issues, issues=issues)


def build_repair_prompt(issues: list[FactIssue]) -> str:
    lines = ["以下事实与 Canon DB 不一致，请重写并修正："]
    for i, issue in enumerate(issues, 1):
        lines.append(f"{i}) [{issue.code}] {issue.message} fact={issue.fact}")
    lines.append("请保持剧情连贯，并在无法确认时明确写“资料不足/版本不一致”。")
    return "\n".join(lines)
