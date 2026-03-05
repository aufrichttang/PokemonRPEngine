from __future__ import annotations

import uuid

from app.battle.fast_resolver import is_battle_turn, resolve_fast_battle
from app.db.models import Session as StorySession


def _session() -> StorySession:
    return StorySession(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="test",
        canon_gen=9,
        canon_game="sv",
        custom_lore_enabled=False,
        battle_mode="fast",
    )


def test_is_battle_turn_keywords() -> None:
    assert is_battle_turn("我要挑战道馆并发动招式") is True
    assert is_battle_turn("我们去逛街聊天") is False


def test_fast_resolver_returns_summary() -> None:
    sess = _session()
    summary = resolve_fast_battle(
        session_obj=sess,
        user_text="我发起战斗并使用火系招式",
        assistant_text="【旁白】你冲向对手。",
    )
    assert summary.triggered is True
    assert summary.summary is not None
    assert summary.summary["mode"] == "fast_v2"
    assert isinstance(summary.summary.get("key_turns"), list)
    assert isinstance(summary.summary.get("next_options"), list)
    assert "battle_text" in summary.summary
