from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderMetrics:
    provider: str
    latency_ms: int
    token_usage: dict[str, Any] | None = None
    status: str = "ok"


class LLMProvider(ABC):
    last_metrics: ProviderMetrics | None = None

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool,
        json_mode: bool = False,
        **params: Any,
    ) -> str | AsyncIterator[str]:
        raise NotImplementedError
