from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

PACE_FAST = "fast"
PACE_BALANCED = "balanced"
PACE_EPIC = "epic"
PACE_VALUES = {PACE_FAST, PACE_BALANCED, PACE_EPIC}


@dataclass(frozen=True)
class BudgetProfile:
    pace: str
    target_tokens: int
    short_window_turns: int
    max_canon_facts: int
    max_recalls: int
    max_open_threads: int
    include_story_blueprint: bool
    include_romance_candidates: bool
    include_legendary_web: bool
    include_gym_plan: bool


@dataclass
class InjectionStats:
    estimated_tokens: int
    sections_used: list[str]
    sections_trimmed: list[str]
    pace: str
    quality_mode: str


@dataclass
class SectionBlock:
    name: str
    text: str
    priority: int  # 0 = never trim, 1 = trim last, 2 = optional


def normalize_pace(value: str | None) -> str:
    v = (value or PACE_BALANCED).strip().lower()
    return v if v in PACE_VALUES else PACE_BALANCED


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # rough zh ratio in this project
    return max(1, int(math.ceil(len(text) / 1.7)))


def resolve_budget_profile(
    *,
    pace: str,
    user_text: str,
    story_progress: dict[str, Any],
    battle_mode: str,
) -> BudgetProfile:
    normalized = normalize_pace(pace)
    lowered = (user_text or "").lower()

    asks_lore = any(
        key in lowered
        for key in (
            "背景",
            "设定",
            "世界观",
            "神兽",
            "历史",
            "真相",
            "细节",
            "深聊",
            "lore",
            "legendary",
            "romance",
        )
    )
    chapter = int(story_progress.get("chapter", 1) or 1)
    objective_status = str(story_progress.get("objective_status", "pending") or "pending").lower()
    climax = chapter >= 7 or objective_status in {"critical", "boss", "climax"}
    battle_turn = battle_mode == "fast" and any(
        key in lowered for key in ("战斗", "对战", "决斗", "boss")
    )

    if normalized == PACE_FAST:
        base = BudgetProfile(
            pace=normalized,
            target_tokens=1000,
            short_window_turns=2,
            max_canon_facts=4,
            max_recalls=4,
            max_open_threads=3,
            include_story_blueprint=False,
            include_romance_candidates=False,
            include_legendary_web=False,
            include_gym_plan=False,
        )
    elif normalized == PACE_EPIC:
        base = BudgetProfile(
            pace=normalized,
            target_tokens=2200,
            short_window_turns=6,
            max_canon_facts=8,
            max_recalls=8,
            max_open_threads=5,
            include_story_blueprint=True,
            include_romance_candidates=True,
            include_legendary_web=True,
            include_gym_plan=True,
        )
    else:
        base = BudgetProfile(
            pace=PACE_BALANCED,
            target_tokens=1400,
            short_window_turns=4,
            max_canon_facts=6,
            max_recalls=6,
            max_open_threads=4,
            include_story_blueprint=False,
            include_romance_candidates=False,
            include_legendary_web=False,
            include_gym_plan=False,
        )

    short_turns = base.short_window_turns
    if battle_turn:
        short_turns = max(2, short_turns - 1)
    if climax and normalized != PACE_FAST:
        short_turns = min(6, short_turns + 1)

    target_tokens = base.target_tokens
    if battle_turn and normalized == PACE_FAST:
        target_tokens = min(target_tokens, 900)
    if climax and normalized == PACE_EPIC:
        target_tokens = max(target_tokens, 2200)

    return BudgetProfile(
        pace=base.pace,
        target_tokens=target_tokens,
        short_window_turns=short_turns,
        max_canon_facts=base.max_canon_facts,
        max_recalls=base.max_recalls,
        max_open_threads=base.max_open_threads,
        include_story_blueprint=base.include_story_blueprint or asks_lore,
        include_romance_candidates=base.include_romance_candidates or asks_lore,
        include_legendary_web=base.include_legendary_web or asks_lore,
        include_gym_plan=base.include_gym_plan or asks_lore,
    )


def apply_budget(
    sections: list[SectionBlock],
    *,
    target_tokens: int,
    pace: str,
    quality_mode: str,
) -> tuple[str, InjectionStats]:
    selected: list[str] = []
    sections_used: list[str] = []
    sections_trimmed: list[str] = []
    token_used = 0

    for section in sorted(sections, key=lambda item: item.priority):
        text = section.text.strip()
        if not text:
            continue
        cost = estimate_tokens(text)
        if section.priority == 0:
            selected.append(text)
            sections_used.append(section.name)
            token_used += cost
            continue
        if token_used + cost <= target_tokens:
            selected.append(text)
            sections_used.append(section.name)
            token_used += cost
        else:
            sections_trimmed.append(section.name)

    payload = "\n\n".join(selected).strip()
    stats = InjectionStats(
        estimated_tokens=estimate_tokens(payload),
        sections_used=sections_used,
        sections_trimmed=sections_trimmed,
        pace=normalize_pace(pace),
        quality_mode=quality_mode,
    )
    return payload, stats

