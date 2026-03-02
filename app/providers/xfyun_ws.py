from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from email.utils import format_datetime
from typing import Any
from urllib.parse import urlencode, urlparse

import websockets

from app.core.config import Settings
from app.providers.base import LLMProvider, ProviderMetrics


def build_ws_authorized_url(
    base_ws_url: str,
    api_key: str,
    api_secret: str,
    dt: datetime | None = None,
) -> str:
    dt = dt or datetime.now(UTC)
    date_str = format_datetime(dt, usegmt=True)

    parsed = urlparse(base_ws_url)
    host = parsed.netloc
    path = parsed.path

    request_line = f"GET {path} HTTP/1.1"
    canonical = f"host: {host}\ndate: {date_str}\n{request_line}"
    signature = base64.b64encode(
        hmac.new(api_secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    auth_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(auth_origin.encode("utf-8")).decode("utf-8")
    query = urlencode({"authorization": authorization, "date": date_str, "host": host})
    return f"{base_ws_url}?{query}"


class XfyunWsProvider(LLMProvider):
    name = "xfyun_ws"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool,
        json_mode: bool = False,
        **params: Any,
    ) -> str | AsyncIterator[str]:
        ws_url = build_ws_authorized_url(
            self.settings.xf_base_url_ws,
            self.settings.xf_api_key,
            self.settings.xf_api_secret,
        )

        payload = {
            "header": {"app_id": self.settings.xf_appid},
            "parameter": {"chat": {"domain": self.settings.xf_model_id, "temperature": 0.8}},
            "payload": {"message": {"text": messages}},
        }
        if json_mode:
            payload["parameter"]["chat"]["response_format"] = {"type": "json_object"}
        payload.update(params)

        start = time.perf_counter()

        async def ws_stream() -> AsyncIterator[str]:
            async with websockets.connect(ws_url) as websocket:
                await websocket.send(json.dumps(payload, ensure_ascii=False))
                async for raw in websocket:
                    obj = json.loads(raw)
                    delta = (
                        obj.get("payload", {})
                        .get("choices", {})
                        .get("text", [{}])[0]
                        .get("content", "")
                    )
                    if delta:
                        yield delta
                    status = obj.get("header", {}).get("status")
                    if status == 2:
                        break
            self.last_metrics = ProviderMetrics(
                provider=self.name,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )

        if stream:
            return ws_stream()

        text_parts: list[str] = []
        async for part in ws_stream():
            text_parts.append(part)
        await asyncio.sleep(0)
        return "".join(text_parts)
