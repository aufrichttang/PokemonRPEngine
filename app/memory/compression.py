from __future__ import annotations

from app.core.config import Settings
from app.memory.schemas import RecallItem, RetrievalResult
from app.utils.text import clamp_text


def compress_retrieval(result: RetrievalResult, settings: Settings) -> RetrievalResult:
    canon = result.canon_facts[: settings.max_canon_facts]
    recalls = sorted(result.recalls, key=lambda x: (x.score, x.importance), reverse=True)[
        : settings.max_recalls
    ]
    threads = result.open_threads[: settings.max_open_threads]

    for item in canon:
        item["event_text"] = clamp_text(item["event_text"], 80)

    formatted_recalls: list[RecallItem] = []
    for r in recalls:
        r.chunk_text = clamp_text(r.chunk_text, 120)
        formatted_recalls.append(r)

    for t in threads:
        t["thread_text"] = clamp_text(t["thread_text"], 60)

    total_chars = sum(len(x["event_text"]) for x in canon)
    total_chars += sum(len(x.chunk_text) for x in formatted_recalls)
    total_chars += sum(len(x["thread_text"]) for x in threads)

    budget = settings.max_prompt_tokens_budget
    while total_chars > budget and formatted_recalls:
        removed = formatted_recalls.pop()
        total_chars -= len(removed.chunk_text)

    while total_chars > budget and threads:
        removed = threads.pop()
        total_chars -= len(removed["thread_text"])

    return RetrievalResult(
        canon_facts=canon,
        recalls=formatted_recalls,
        open_threads=threads,
        debug=result.debug,
    )
