from __future__ import annotations

import hashlib
import re
from typing import Any

# Matches lines like:
# 1) xxx / 1. xxx / 1、xxx / ① xxx / - xxx / * xxx
CHOICE_LINE_RE = re.compile(r"^\s*(?:[1-9]\d*\s*[\)\.、:]|[①②③④⑤⑥⑦⑧⑨⑩]|[-*])\s*(.+)$")
ACTION_BLOCK_RE = re.compile(
    r"(?:【可选动作】|\[可选动作\]|Action\s*Options?)\s*[:：]?\s*([\s\S]+)$",
    re.IGNORECASE,
)


def _stable_option_id(text: str, idx: int) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"opt-{idx}-{digest}"


def _clean_option_text(text: str) -> str:
    cleaned = text.strip().strip('"\'`').strip()
    cleaned = re.sub(r"^\s*[-*]+\s*", "", cleaned)
    cleaned = re.sub(r"^\s*\d+\s*[:：]\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


class ActionOptionService:
    @staticmethod
    def extract_action_options(
        structured_payload: dict[str, Any] | None,
        assistant_text: str,
    ) -> list[dict[str, str]]:
        payload = structured_payload if isinstance(structured_payload, dict) else {}
        out: list[dict[str, str]] = []

        raw = payload.get("action_options")
        if isinstance(raw, list):
            for idx, item in enumerate(raw, 1):
                if isinstance(item, str):
                    text = _clean_option_text(item)
                    send_text = text
                    option_id = _stable_option_id(send_text, idx)
                elif isinstance(item, dict):
                    text = _clean_option_text(str(item.get("text") or ""))
                    send_text = _clean_option_text(str(item.get("send_text") or text))
                    option_id = str(item.get("id") or _stable_option_id(send_text, idx))
                else:
                    continue

                if not text or not send_text:
                    continue
                if any(k in text.lower() for k in ("facts_used", "state_update", "open_threads_update")):
                    continue
                out.append({"id": option_id, "text": text, "send_text": send_text})

        if out:
            return out[:6]

        # Fallback from narrative block in assistant text.
        source_text = assistant_text or ""
        action_block = ACTION_BLOCK_RE.search(source_text)
        if action_block:
            source_text = action_block.group(1)

        candidates: list[str] = []
        for line in source_text.splitlines():
            match = CHOICE_LINE_RE.match(line)
            if not match:
                continue
            val = _clean_option_text(match.group(1))
            if val:
                candidates.append(val)

        deduped: list[str] = []
        seen = set()
        for item in candidates:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        for idx, text in enumerate(deduped[:5], 1):
            out.append({"id": _stable_option_id(text, idx), "text": text, "send_text": text})

        return out

    @staticmethod
    def build_dynamic_fallback_options(user_text: str, primary_text: str) -> list[dict[str, str]]:
        """Last-resort local fallback to keep gameplay moving when model output is malformed."""
        theme = (primary_text or user_text or "主线").strip()
        snippets = [
            f"推进当前主线：围绕“{theme[:28]}”继续行动",
            "调查关键线索：追踪当前场景中的可疑信息",
            "整备队伍与背包：恢复状态并调整下一步策略",
        ]
        out: list[dict[str, str]] = []
        for i, text in enumerate(snippets, 1):
            out.append({"id": _stable_option_id(text, i), "text": text, "send_text": text})
        return out
