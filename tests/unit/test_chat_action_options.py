from __future__ import annotations

from app.core.config import Settings
from app.memory.schemas import FakeEmbeddingProvider
from app.providers.mock import MockProvider
from app.services.chat_service import ChatService


def _service() -> ChatService:
    settings = Settings(
        DATABASE_URL="sqlite:///./x.db",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="x",
    )
    return ChatService(
        settings=settings,
        provider=MockProvider(),
        embedding_provider=FakeEmbeddingProvider(),
    )


def test_extract_action_options_from_json() -> None:
    service = _service()
    structured = {
        "action_options": [
            {"id": "a", "text": "推进剧情", "send_text": "我选择推进剧情"},
            {"id": "b", "text": "调查", "send_text": "我去调查"},
        ]
    }
    out = service._extract_action_options(structured, "")
    assert len(out) == 2
    assert out[0]["id"] == "a"


def test_extract_action_options_fallback_to_numbered_text() -> None:
    service = _service()
    assistant_text = """【可选动作】\n1) 调查洞穴\n2) 返回补给点\n3) 挑战道馆"""
    out = service._extract_action_options({}, assistant_text)
    assert [x["text"] for x in out] == ["调查洞穴", "返回补给点", "挑战道馆"]


def test_extract_action_options_filters_json_noise() -> None:
    service = _service()
    structured = {
        "action_options": [
            {"id": "ok", "text": "推进主线", "send_text": "我推进主线"},
            {"id": "bad1", "text": "facts_used", "send_text": "facts_used"},
            {"id": "bad2", "text": "state_update", "send_text": "state_update"},
        ]
    }
    out = service._extract_action_options(structured, "")
    assert [x["id"] for x in out] == ["ok"]
