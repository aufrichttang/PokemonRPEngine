from __future__ import annotations

import re


def split_sentences(text: str) -> list[str]:
    normalized = text.replace("\r", "\n").strip()
    parts = re.split(r"(?<=[。！？!?\n])", normalized)
    return [p.strip() for p in parts if p.strip()]


def clamp_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
