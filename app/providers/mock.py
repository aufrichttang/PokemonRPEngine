from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from app.providers.base import LLMProvider, ProviderMetrics


class MockProvider(LLMProvider):
    """Deterministic provider for tests and local bootstrapping."""

    name = "mock"

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool,
        json_mode: bool = False,
        **params: Any,
    ) -> str | AsyncIterator[str]:
        start = time.perf_counter()
        user_msg = messages[-1]["content"] if messages else ""
        canon_block = self._extract_block(messages, "CANON_FACTS")
        planner_mode = any(
            "PIPELINE_STAGE" in m.get("content", "") and "PLANNER" in m.get("content", "")
            for m in messages
        )
        locked_options = self._extract_locked_options(messages)

        if planner_mode:
            reply_json = {
                "narrative": {"primary": "【旁白】你已抵达新的剧情节点，局势正在升温。"},
                "action_options": (
                    locked_options
                    if locked_options
                    else [
                        {"id": "opt-1", "text": "继续向前探索", "send_text": "我继续向前探索"},
                        {"id": "opt-2", "text": "调查附近异动", "send_text": "我先调查附近异动"},
                        {"id": "opt-3", "text": "返回补给站整备", "send_text": "我先回补给站整备"},
                    ]
                ),
            }
            reply = json.dumps(reply_json, ensure_ascii=False)
        else:
            options = locked_options or [
                {"id": "opt-1", "text": "继续向前探索", "send_text": "我继续向前探索"},
                {"id": "opt-2", "text": "调查附近异动", "send_text": "我先调查附近异动"},
                {"id": "opt-3", "text": "返回补给站整备", "send_text": "我先回补给站整备"},
            ]
            reply = (
                "【旁白】你沿着道路继续前进，并获得了一枚旧徽章。\n"
                f"【对白】向导：已记录你的行动「{user_msg[:80]}」。\n"
                f'【设定引用】{canon_block or "暂无硬事实，继续探索。"}\n\n'
                f"<!--JSON-->{json.dumps({'facts_used': [], 'state_update': {}, 'open_threads_update': [], 'action_options': options}, ensure_ascii=False)}<!--/JSON-->"
            )

        elapsed = int((time.perf_counter() - start) * 1000)
        self.last_metrics = ProviderMetrics(
            provider=self.name,
            latency_ms=elapsed,
            token_usage={"prompt_tokens": 0, "completion_tokens": max(1, len(reply) // 2)},
        )

        if not stream:
            return reply

        async def streamer() -> AsyncIterator[str]:
            for i in range(0, len(reply), 60):
                await asyncio.sleep(0)
                yield reply[i : i + 60]

        return streamer()

    @staticmethod
    def _extract_block(messages: list[dict[str, str]], block_name: str) -> str:
        combined = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system")
        pattern = rf"【{block_name}】\n(.+?)(?:\n\n【|$)"
        match = re.search(pattern, combined, flags=re.DOTALL)
        if not match:
            return ""
        line = match.group(1).strip().splitlines()[0] if match.group(1).strip() else ""
        return line[:120]

    @staticmethod
    def _extract_locked_options(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        combined = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system")
        match = re.search(r"LOCKED_ACTION_OPTIONS=(\[[\s\S]*\])", combined)
        if not match:
            return []
        raw = match.group(1).strip()
        try:
            payload = json.loads(raw)
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        out: list[dict[str, str]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            send_text = str(item.get("send_text") or text).strip()
            option_id = str(item.get("id") or f"opt-{len(out)+1}")
            if not text or not send_text:
                continue
            out.append({"id": option_id, "text": text, "send_text": send_text})
        return out[:6]
