from __future__ import annotations

import asyncio
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
        reply = (
            "【旁白】你沿着道路继续前进，并获得了一枚旧徽章。\n"
            f"【对白】向导：已记录你的行动「{user_msg[:80]}」。\n"
            f'【设定引用】{canon_block or "暂无硬事实，继续探索。"}\n\n'
            '<!--JSON-->{"facts_used":[],"state_update":{},"open_threads_update":[]}<!--/JSON-->'
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
