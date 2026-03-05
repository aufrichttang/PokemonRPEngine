from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from app.db.models import Session as StorySession

BATTLE_HINTS = (
    "战斗",
    "对战",
    "招式",
    "技能",
    "攻击",
    "道馆",
    "馆主",
    "野生",
    "捕捉",
    "精灵球",
)


@dataclass
class BattleSummary:
    triggered: bool
    summary: dict[str, Any] | None


def is_battle_turn(user_text: str) -> bool:
    text = user_text.lower()
    return any(k in text for k in BATTLE_HINTS)


def resolve_fast_battle(
    *,
    session_obj: StorySession,
    user_text: str,
    assistant_text: str,
) -> BattleSummary:
    if session_obj.battle_mode != "fast" or not is_battle_turn(user_text):
        return BattleSummary(triggered=False, summary=None)

    digest = hashlib.sha1(f"{session_obj.id}|{user_text}".encode()).digest()
    seed = int.from_bytes(digest[:4], "big")
    rounds = 1 + (seed % 3)
    momentum = ["开场压制", "中盘反打", "残局绝杀"][seed % 3]
    result = ["小胜", "险胜", "平局脱离", "被压制后撤"][seed % 4]
    hp_our = -(8 + (seed % 28))
    hp_enemy = -(12 + ((seed >> 3) % 36))

    tactical_reasons = [
        "利用换位吃掉关键招式，再反打收割。",
        "优先抢节奏，用属性克制逼对方交保命资源。",
        "先控场后爆发，避免被对方先手连锁。",
        "用诱饵位骗出大招，再让主力完成终结。",
    ]
    tactical_reasoning = tactical_reasons[(seed >> 5) % len(tactical_reasons)]

    key_turns = [
        {"turn": 1, "event": "首回合抢到站位优势，压低对手节奏。"},
        {"turn": max(1, rounds - 1), "event": "关键换位规避克制，保住主力血线。"},
        {"turn": rounds, "event": "抓住破绽完成收官判定。"},
    ]
    next_options = [
        {"id": "battle-heal", "text": "先补给稳住血线", "send_text": "我先补给并稳住队伍血线。"},
        {"id": "battle-press", "text": "趁势追击扩大优势", "send_text": "我选择趁势追击，扩大优势。"},
        {"id": "battle-switch", "text": "换位观察下一只", "send_text": "我先换位，观察对手下一只。"},
    ]

    summary = {
        "mode": "fast_v2",
        "result": result,
        "momentum": momentum,
        "rounds": rounds,
        "our_hp_change": hp_our,
        "enemy_hp_change": hp_enemy,
        "key_turns": key_turns,
        "tactical_reasoning": tactical_reasoning,
        "next_options": next_options,
    }

    battle_text = (
        "\n\n【快战术 2.0】"
        f"\n- 节奏：{momentum}"
        f"\n- 结果：{result}（{rounds}回合）"
        f"\n- 关键：{key_turns[1]['event']}"
        f"\n- 战术：{tactical_reasoning}"
    )

    return BattleSummary(
        triggered=True,
        summary={
            **summary,
            "battle_text": battle_text,
            "assistant_preview": assistant_text[:160],
        },
    )
