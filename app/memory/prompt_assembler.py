from __future__ import annotations

from app.core.config import Settings
from app.db.models import Turn
from app.memory.policies import DEFAULT_SYSTEM_PROMPT
from app.memory.schemas import QueryPlan, RetrievalResult
from app.utils.text import clamp_text


def build_injection_block(
    retrieval: RetrievalResult,
    recent_turns: list[Turn],
    settings: Settings,
) -> str:
    canon_lines = [
        f"{idx}) {item['event_text']}" for idx, item in enumerate(retrieval.canon_facts, 1)
    ]
    recall_lines = [
        f"- (turn {r.turn_index}) {clamp_text(r.chunk_text, 120)} [score={r.score}]"
        for r in retrieval.recalls
    ]
    thread_lines = [f"- {t['thread_text']}" for t in retrieval.open_threads]

    short_window_lines: list[str] = []
    for t in recent_turns[-settings.short_window_turns :]:
        short_window_lines.append(f"(turn {t.turn_index} user) {clamp_text(t.user_text, 160)}")
        short_window_lines.append(
            f"(turn {t.turn_index} assistant) {clamp_text(t.assistant_text, 160)}"
        )

    parts = [
        "【CANON_FACTS】\n" + ("\n".join(canon_lines) if canon_lines else "1) 暂无确认事实"),
        "【RELEVANT_RECALLS】\n" + ("\n".join(recall_lines) if recall_lines else "- 暂无召回"),
        "【OPEN_THREADS】\n" + ("\n".join(thread_lines) if thread_lines else "- 暂无悬而未决线索"),
        "【SHORT_WINDOW】\n" + ("\n".join(short_window_lines) if short_window_lines else "(empty)"),
    ]
    return "\n\n".join(parts)


def assemble_messages(
    user_text: str,
    query_plan: QueryPlan,
    retrieval: RetrievalResult,
    recent_turns: list[Turn],
    settings: Settings,
) -> tuple[list[dict[str, str]], str]:
    _ = query_plan
    injection = build_injection_block(retrieval, recent_turns, settings)
    messages = [
        {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
        {"role": "system", "content": injection},
        {"role": "user", "content": user_text},
    ]
    return messages, injection
