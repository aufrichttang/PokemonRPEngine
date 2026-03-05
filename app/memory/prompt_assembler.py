from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.db.models import Session as StorySession
from app.db.models import Turn
from app.memory.budgeter import (
    InjectionStats,
    SectionBlock,
    apply_budget,
    normalize_pace,
    resolve_budget_profile,
)
from app.memory.policies import DEFAULT_SYSTEM_PROMPT
from app.memory.schemas import QueryPlan, RetrievalResult
from app.utils.text import clamp_text

TYPE_ZH = {
    "normal": "一般",
    "fire": "火",
    "water": "水",
    "electric": "电",
    "grass": "草",
    "ice": "冰",
    "fighting": "格斗",
    "poison": "毒",
    "ground": "地面",
    "flying": "飞行",
    "psychic": "超能力",
    "bug": "虫",
    "rock": "岩石",
    "ghost": "幽灵",
    "dragon": "龙",
    "dark": "恶",
    "steel": "钢",
    "fairy": "妖精",
}


def _types_zh(types: list[str]) -> str:
    if not types:
        return "未知"
    return "/".join(TYPE_ZH.get(t, t) for t in types)


def _story_quality_mode(*, story_progress: dict[str, Any], user_text: str) -> str:
    chapter = int(story_progress.get("chapter", 1) or 1)
    status = str(story_progress.get("objective_status", "pending") or "pending").lower()
    lowered = (user_text or "").lower()
    if chapter >= 7:
        return "chapter_climax"
    if status in {"critical", "boss", "climax"}:
        return "chapter_climax"
    if any(key in lowered for key in ("终局", "决战", "神兽危机", "boss", "final")):
        return "chapter_climax"
    return "normal"


def _build_story_blueprint_map(world_profile: dict[str, Any]) -> dict[int, dict[str, Any]]:
    chapter_map: dict[int, dict[str, Any]] = {}
    acts = world_profile.get("story_blueprint", {}).get("acts", [])
    if not isinstance(acts, list):
        return chapter_map
    for act in acts:
        if not isinstance(act, dict):
            continue
        chapters = act.get("chapters", [])
        if not isinstance(chapters, list):
            continue
        for chapter in chapters:
            if not isinstance(chapter, dict):
                continue
            idx = int(chapter.get("chapter_index", 0) or 0)
            if idx > 0:
                chapter_map[idx] = chapter
    return chapter_map


def _extract_faction_pressures(kernel_faction: dict[str, Any]) -> list[tuple[str, int]]:
    pressures: list[tuple[str, int]] = []
    for group, payload in kernel_faction.items():
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if isinstance(value, int):
                pressures.append((f"{group}.{key}", value))
    pressures.sort(key=lambda pair: pair[1], reverse=True)
    return pressures


def build_injection_block(
    session_obj: StorySession,
    retrieval: RetrievalResult,
    recent_turns: list[Turn],
    settings: Settings,
    battle_mode: str,
    *,
    user_text: str,
    pace: str,
) -> tuple[str, InjectionStats]:
    world_profile = session_obj.world_profile if isinstance(session_obj.world_profile, dict) else {}
    player_profile = session_obj.player_profile if isinstance(session_obj.player_profile, dict) else {}
    player_state = session_obj.player_state if isinstance(session_obj.player_state, dict) else {}
    story_progress = (
        player_state.get("story_progress", {})
        if isinstance(player_state.get("story_progress"), dict)
        else {}
    )

    quality_mode = _story_quality_mode(story_progress=story_progress, user_text=user_text)
    profile = resolve_budget_profile(
        pace=pace,
        user_text=user_text,
        story_progress=story_progress,
        battle_mode=battle_mode,
    )

    canon_facts = retrieval.canon_facts[: profile.max_canon_facts]
    recalls = retrieval.recalls[: profile.max_recalls]
    open_threads = retrieval.open_threads[: profile.max_open_threads]
    short_turns = recent_turns[-profile.short_window_turns :]

    romance_candidates = [
        c for c in (world_profile.get("romance_candidates") or []) if isinstance(c, dict)
    ]
    legendary_nodes = [
        n
        for n in (world_profile.get("legendary_web", {}).get("nodes", []) or [])
        if isinstance(n, dict)
    ]
    sacrifice_stakes = [
        str(item)
        for item in (world_profile.get("sacrifice_stakes") or [])
        if isinstance(item, str) and item.strip()
    ]
    gym_plan = [g for g in (session_obj.gym_plan or []) if isinstance(g, dict)]
    starter_options = [s for s in (session_obj.starter_options or []) if isinstance(s, dict)]

    kernel_summary = (
        player_state.get("kernel_summary", {})
        if isinstance(player_state.get("kernel_summary"), dict)
        else {}
    )
    kernel_lore = kernel_summary.get("lore", {}) if isinstance(kernel_summary.get("lore"), dict) else {}
    kernel_time = kernel_summary.get("time", {}) if isinstance(kernel_summary.get("time"), dict) else {}
    kernel_faction = (
        kernel_summary.get("faction", {}) if isinstance(kernel_summary.get("faction"), dict) else {}
    )
    kernel_warnings = (
        [str(item) for item in kernel_summary.get("warnings", []) if str(item).strip()]
        if isinstance(kernel_summary.get("warnings"), list)
        else []
    )
    faction_pressures = _extract_faction_pressures(kernel_faction)

    chapter_map = _build_story_blueprint_map(world_profile)
    current_act = int(story_progress.get("act", 1) or 1)
    current_chapter = int(story_progress.get("chapter", 1) or 1)
    current_objective = str(story_progress.get("objective") or "").strip()
    current_status = str(story_progress.get("objective_status", "pending") or "pending").strip()
    if not current_objective and current_chapter in chapter_map:
        current_objective = str(chapter_map[current_chapter].get("objective", "")).strip()

    canon_lines = [
        f"{idx}) {clamp_text(item.get('event_text', ''), 72)}"
        for idx, item in enumerate(canon_facts, 1)
    ]
    recall_lines = [
        f"- (turn {r.turn_index}) {clamp_text(r.chunk_text, 80)} [score={r.score}]"
        for r in recalls
    ]
    thread_lines = [f"- {clamp_text(str(t.get('thread_text', '')), 48)}" for t in open_threads]

    short_window_lines: list[str] = []
    for turn in short_turns:
        short_window_lines.append(f"(turn {turn.turn_index} user) {clamp_text(turn.user_text, 92)}")
        short_window_lines.append(
            f"(turn {turn.turn_index} assistant) {clamp_text(turn.assistant_text, 92)}"
        )

    sections: list[SectionBlock] = [
        SectionBlock(
            name="CANON_FACTS",
            priority=0,
            text="【CANON_FACTS】\n" + ("\n".join(canon_lines) if canon_lines else "1) 暂无确认事实"),
        ),
        SectionBlock(
            name="CURRENT_CHAPTER_OBJECTIVE",
            priority=0,
            text=(
                "【CURRENT_CHAPTER_OBJECTIVE】\n"
                f"- 当前幕：第{current_act}幕\n"
                f"- 当前章：第{current_chapter}章\n"
                f"- 本章目标：{current_objective or '推进主线并锁定关键线索'}\n"
                f"- 状态：{current_status}"
            ),
        ),
        SectionBlock(
            name="KERNEL_CAPSULE",
            priority=0,
            text=(
                "【KERNEL_CAPSULE】\n"
                f"- phase: {kernel_lore.get('protocol_phase', 'silent_sampling')}\n"
                f"- instability: {kernel_lore.get('cycle_instability', 0)}\n"
                f"- debt: {kernel_time.get('temporal_debt', 0)}\n"
                f"- cohesion: {kernel_time.get('narrative_cohesion', 0)}\n"
                "- top_pressure: "
                + (", ".join(f"{name}:{score}" for name, score in faction_pressures[:2]) or "none")
                + "\n- warnings: "
                + (", ".join(kernel_warnings[:2]) if kernel_warnings else "none")
            ),
        ),
        SectionBlock(
            name="PLAYER_PROFILE",
            priority=1,
            text=(
                "【PLAYER_PROFILE】\n"
                f"- 名字：{player_profile.get('name', '未命名')}\n"
                f"- 性别：{player_profile.get('gender', '未设定')}  年龄：{player_profile.get('age', '?')}\n"
                f"- 个性：{clamp_text(str(player_profile.get('personality', '未设定')), 36)}"
            ),
        ),
        SectionBlock(
            name="RELEVANT_RECALLS",
            priority=1,
            text="【RELEVANT_RECALLS】\n" + ("\n".join(recall_lines) if recall_lines else "- 暂无可回忆片段"),
        ),
        SectionBlock(
            name="OPEN_THREADS",
            priority=1,
            text="【OPEN_THREADS】\n" + ("\n".join(thread_lines) if thread_lines else "- 暂无线索"),
        ),
        SectionBlock(
            name="SHORT_WINDOW",
            priority=1,
            text="【SHORT_WINDOW】\n" + ("\n".join(short_window_lines) if short_window_lines else "(empty)"),
        ),
    ]

    if profile.include_story_blueprint:
        chapter_lines: list[str] = []
        for idx in (current_chapter, current_chapter + 1):
            chapter = chapter_map.get(idx)
            if not isinstance(chapter, dict):
                continue
            title = str(chapter.get("title") or f"第{idx}章")
            objective = clamp_text(str(chapter.get("objective") or ""), 42)
            chapter_lines.append(f"- 第{idx}章 {title}：{objective}")
        sections.append(
            SectionBlock(
                name="STORY_BLUEPRINT",
                priority=2,
                text="【STORY_BLUEPRINT】\n" + ("\n".join(chapter_lines) if chapter_lines else "- 当前章节蓝图未加载"),
            )
        )

    if profile.include_legendary_web:
        legendary_lines = [
            (
                f"- {node.get('name_zh', '未知神兽')} / "
                f"权柄:{node.get('domain', '未知')} / 风险:{node.get('risk_level', '中')}"
            )
            for node in legendary_nodes[:2]
        ]
        sections.append(
            SectionBlock(
                name="LEGENDARY_WEB",
                priority=2,
                text="【LEGENDARY_WEB】\n" + ("\n".join(legendary_lines) if legendary_lines else "- 暂无神兽关系"),
            )
        )

    if profile.include_romance_candidates:
        romance_lines = [
            f"- {c.get('name', '未知角色')}：{clamp_text(str(c.get('route_hint', '关键角色')), 32)}"
            for c in romance_candidates[:2]
        ]
        sections.append(
            SectionBlock(
                name="ROMANCE_CANDIDATES",
                priority=2,
                text="【ROMANCE_CANDIDATES】\n" + ("\n".join(romance_lines) if romance_lines else "- 暂无候选"),
            )
        )

    if profile.include_gym_plan:
        gym_lines = [
            (
                f"{g.get('index', idx)}) {g.get('city_name', '未知城市')} - "
                f"{g.get('gym_type', 'normal')}系 / 馆主 {g.get('leader_name', '未知')}"
            )
            for idx, g in enumerate(gym_plan[:3], 1)
        ]
        sections.append(
            SectionBlock(
                name="GYM_PLAN",
                priority=2,
                text="【GYM_PLAN】\n" + ("\n".join(gym_lines) if gym_lines else "- 道馆计划未加载"),
            )
        )

    if sacrifice_stakes:
        sections.append(
            SectionBlock(
                name="SACRIFICE_STAKES",
                priority=2,
                text="【SACRIFICE_STAKES】\n- " + clamp_text(sacrifice_stakes[0], 56),
            )
        )

    if starter_options and len(short_turns) <= 1:
        starter_lines = [
            (
                f"- {s.get('name_zh', s.get('slug_id'))}"
                f"（{_types_zh(s.get('types', []) if isinstance(s.get('types'), list) else [])}）"
            )
            for s in starter_options[:3]
        ]
        sections.append(
            SectionBlock(
                name="STARTER_OPTIONS",
                priority=2,
                text="【STARTER_OPTIONS】\n" + "\n".join(starter_lines),
            )
        )

    injection, stats = apply_budget(
        sections,
        target_tokens=profile.target_tokens,
        pace=normalize_pace(pace),
        quality_mode=quality_mode,
    )
    return injection, stats


def assemble_messages(
    session_obj: StorySession,
    user_text: str,
    query_plan: QueryPlan,
    retrieval: RetrievalResult,
    recent_turns: list[Turn],
    settings: Settings,
    battle_mode: str,
    battle_hint: str | None = None,
    *,
    pace: str = "balanced",
) -> tuple[list[dict[str, str]], str, InjectionStats]:
    _ = query_plan
    injection, injection_stats = build_injection_block(
        session_obj,
        retrieval,
        recent_turns,
        settings,
        battle_mode,
        user_text=user_text,
        pace=pace,
    )

    messages = [
        {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
        {"role": "system", "content": injection},
    ]
    if battle_hint:
        messages.append(
            {
                "role": "system",
                "content": (
                    "【BATTLE_MODE】fast\n"
                    "战斗文本必须短而清晰，优先给出关键判定、结果和下一步建议，避免冗长回合播报。\n"
                    f"{battle_hint}"
                ),
            }
        )
    messages.append({"role": "user", "content": user_text})
    return messages, injection, injection_stats

