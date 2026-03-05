from __future__ import annotations

from typing import Any

from app.kernels.rules import legacy_catalog, time_rules


def clamp_0_100(value: int) -> int:
    return max(0, min(100, int(value)))


def infer_legacy_tags(*, text: str, actors: list[str] | None = None) -> list[str]:
    content = f"{text} {' '.join(actors or [])}".lower()
    out: list[str] = []
    for tag, terms in legacy_catalog().items():
        if any(term.lower() in content for term in terms):
            out.append(str(tag))
    return sorted(set(out))


def infer_time_class(
    *,
    canon_level: str,
    source_trust: float,
    conflict_score: int,
    text: str,
) -> str:
    cfg = time_rules().get("classification", {})
    echo_keywords = [str(x) for x in time_rules().get("echo_keywords", [])]
    lowered = text.lower()
    if any(keyword.lower() in lowered for keyword in echo_keywords):
        return "echo"

    fixed_min_trust = float(cfg.get("fixed_min_trust", 0.75))
    fixed_max_conflict = int(cfg.get("fixed_max_conflict", 35))
    fragile_min_conflict = int(cfg.get("fragile_min_conflict", 36))

    if (
        canon_level == "confirmed"
        and source_trust >= fixed_min_trust
        and conflict_score <= fixed_max_conflict
    ):
        return "fixed"
    if canon_level in {"implied", "pending"} or conflict_score >= fragile_min_conflict:
        return "fragile"
    return "unjudged"


def classify_event_metadata(
    *,
    text: str,
    canon_level: str,
    actors: list[str] | None = None,
    witness_count: int = 1,
    source_trust: float | None = None,
    conflict_score: int | None = None,
) -> dict[str, Any]:
    trust = float(source_trust if source_trust is not None else (0.85 if canon_level == "confirmed" else 0.6))
    conflict = int(conflict_score if conflict_score is not None else (45 if canon_level == "conflict" else 25))
    time_class = infer_time_class(
        canon_level=canon_level,
        source_trust=trust,
        conflict_score=conflict,
        text=text,
    )
    return {
        "time_class": time_class,
        "source_trust": max(0.0, min(1.0, trust)),
        "witness_count": max(1, int(witness_count)),
        "narrative_conflict_score": clamp_0_100(conflict),
        "canon_legacy_tags": infer_legacy_tags(text=text, actors=actors),
    }

