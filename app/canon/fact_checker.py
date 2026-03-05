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
JSON_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
JSON_TAIL_PATTERN = re.compile(r"(\{[\s\S]*?\"facts_used\"[\s\S]*\})\s*$", re.IGNORECASE)
JSON_FENCE_UNCLOSED_PATTERN = re.compile(r"```(?:json)?[\s\S]*$", re.IGNORECASE)


@dataclass
class FactIssue:
    code: str
    message: str
    fact: dict[str, Any]


@dataclass
class FactCheckResult:
    ok: bool
    issues: list[FactIssue]


def _default_payload() -> dict[str, Any]:
    return {
        "facts_used": [],
        "state_update": {},
        "open_threads_update": [],
        "action_options": [],
    }


def _parse_json_object(payload: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(payload.strip())
    except json.JSONDecodeError:
        return None
    if isinstance(obj, dict):
        return obj
    return None


def try_extract_structured_json(text: str) -> dict[str, Any] | None:
    for pattern in (JSON_BLOCK_PATTERN, JSON_FENCE_PATTERN):
        matches = pattern.findall(text)
        for payload in reversed(matches):
            parsed = _parse_json_object(payload)
            if parsed is not None:
                return parsed

    unclosed = JSON_FENCE_UNCLOSED_PATTERN.search(text)
    if unclosed:
        payload = unclosed.group(0)
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            parsed = _parse_json_object(payload[start : end + 1])
            if parsed is not None:
                return parsed

    tail = JSON_TAIL_PATTERN.search(text)
    if tail:
        parsed = _parse_json_object(tail.group(1))
        if parsed is not None:
            return parsed

    return None


def extract_structured_json(text: str, *, strict: bool = False) -> dict[str, Any]:
    parsed = try_extract_structured_json(text)
    if parsed is not None:
        return parsed
    if strict:
        return {}
    return _default_payload()


def strip_structured_json(text: str) -> str:
    cleaned = JSON_BLOCK_PATTERN.sub("", text)
    cleaned = JSON_FENCE_PATTERN.sub("", cleaned)
    cleaned = JSON_FENCE_UNCLOSED_PATTERN.sub("", cleaned)

    tail = JSON_TAIL_PATTERN.search(cleaned)
    if tail and _parse_json_object(tail.group(1)) is not None:
        cleaned = cleaned[: tail.start()]

    return cleaned.strip()


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
        if not isinstance(fact, dict):
            continue
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
