from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import Settings
from app.providers.base import LLMProvider, ProviderMetrics


class XfyunHttpProvider(LLMProvider):
    name = "xfyun_http"

    def __init__(self, settings: Settings):
        self.settings = settings

    def _bearer_token(self) -> str:
        """Build bearer token compatible with XFYun v1/v2 gateway variants."""
        key = self.settings.xf_api_key.strip()
        secret = self.settings.xf_api_secret.strip()
        base = self.settings.xf_base_url_http.rstrip("/").lower()

        if ":" in key:
            return key
        # v2 gateway expects api_key:api_secret in bearer token.
        if base.endswith("/v2") and secret:
            return f"{key}:{secret}"
        return key

    def _headers(self) -> dict[str, str]:
        if self.settings.xf_auth_mode == "header_triple":
            return {
                "X-Appid": self.settings.xf_appid,
                "X-Api-Key": self.settings.xf_api_key,
                "X-Api-Secret": self.settings.xf_api_secret,
                "Content-Type": "application/json",
            }
        return {
            "Authorization": f"Bearer {self._bearer_token()}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool,
        json_mode: bool = False,
        **params: Any,
    ) -> str | AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self.settings.xf_model_id,
            "messages": messages,
            "stream": stream,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        payload.update(params)

        endpoint = self.settings.xf_base_url_http.rstrip("/") + "/chat/completions"
        start = time.perf_counter()

        if stream:
            return self._streaming(endpoint=endpoint, payload=payload, start=start)

        retries = self.settings.llm_max_retries
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            last_exc: Exception | None = None
            for attempt in range(retries + 1):
                try:
                    response = await client.post(endpoint, json=payload, headers=self._headers())
                    response.raise_for_status()
                    data = response.json()
                    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    usage = data.get("usage")
                    self.last_metrics = ProviderMetrics(
                        provider=self.name,
                        latency_ms=int((time.perf_counter() - start) * 1000),
                        token_usage=usage,
                    )
                    return text
                except Exception as exc:
                    last_exc = exc
                    if attempt >= retries:
                        break
                    await asyncio.sleep(0.5 * (2**attempt))

        assert last_exc is not None
        raise last_exc

    def _streaming(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
        start: float,
    ) -> AsyncIterator[str]:
        async def iterator() -> AsyncIterator[str]:
            retries = self.settings.llm_max_retries
            last_exc: Exception | None = None
            usage: dict[str, Any] | None = None

            for attempt in range(retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                        async with client.stream(
                            "POST", endpoint, json=payload, headers=self._headers()
                        ) as response:
                            response.raise_for_status()
                            content_type = response.headers.get("content-type", "")
                            if "text/event-stream" not in content_type:
                                body = await response.aread()
                                text = body.decode("utf-8", errors="ignore")
                                for i in range(0, len(text), 80):
                                    await asyncio.sleep(0)
                                    yield text[i : i + 80]
                                break

                            async for line in response.aiter_lines():
                                if not line.startswith("data:"):
                                    continue
                                data = line[5:].strip()
                                if data == "[DONE]":
                                    break
                                try:
                                    payload_obj = json.loads(data)
                                except json.JSONDecodeError:
                                    continue
                                delta = (
                                    payload_obj.get("choices", [{}])[0]
                                    .get("delta", {})
                                    .get("content", "")
                                )
                                if delta:
                                    yield delta
                                if payload_obj.get("usage"):
                                    usage = payload_obj.get("usage")
                            break
                except Exception as exc:
                    last_exc = exc
                    if attempt >= retries:
                        raise
                    await asyncio.sleep(0.5 * (2**attempt))

            self.last_metrics = ProviderMetrics(
                provider=self.name,
                latency_ms=int((time.perf_counter() - start) * 1000),
                token_usage=usage,
            )
            if last_exc:
                _ = last_exc

        return iterator()
