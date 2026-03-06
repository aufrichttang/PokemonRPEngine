from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import Settings
from app.db.models import Session as StorySession
from app.providers.base import LLMProvider
from app.services.opening_story_service import OpeningStoryService
from app.services.session_service import _opening_intro


class JsonProvider(LLMProvider):
    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool,
        json_mode: bool = False,
        **params: Any,
    ) -> str | AsyncIterator[str]:
        return (
            '{"profile_digest_lines":["名字：唐雨","性格：外冷内热","背景：边境小镇幸存者"],'
            '"backstory_scene":"你在矿轨尽头停下脚步，异象残光仍在天幕跳动。'
            '十三岁的那一晚像伤口一样反复撕开，你曾失去重要之人，也从那时立下誓言。",'
            '"transition_line":"当前目标：完成启程并锁定第一枚徽章线索。代价预警：胜利伴随牺牲。"}'
        )


class BrokenProvider(LLMProvider):
    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool,
        json_mode: bool = False,
        **params: Any,
    ) -> str | AsyncIterator[str]:
        return "not-json"


def _world_profile() -> dict[str, Any]:
    return {
        "continent_name": "岚渊大陆",
        "start_town": "野星谷",
        "story_blueprint": {
            "acts": [
                {
                    "chapters": [
                        {
                            "chapter_index": 1,
                            "title": "起始火花",
                            "objective": "在野星谷完成启程并锁定第一枚徽章线索",
                            "sacrifice_cost": "放弃安稳生活，公开站上危险前线",
                        }
                    ]
                }
            ]
        },
        "romance_candidates": [{"name": "顾瑶"}],
        "story_enhancement": {"arc_overview": "三幕八章主线推进"},
    }


def _player_profile() -> dict[str, Any]:
    return {
        "name": "唐雨",
        "gender": "男",
        "age": 14,
        "height_cm": 190,
        "appearance": "银灰短发、轮廓干净",
        "personality": "外冷内热",
        "background": "边境小镇幸存者",
        "detail": "想夺得冠军并解开神兽异象",
        "backstory": {
            "origin": "野星谷矿脉聚落",
            "inciting_incident": "13岁目睹神兽异象暴走事件",
            "scar_and_vow": "哪怕牺牲荣耀也要守住撤离线",
            "past_companion": {"name": "凛司", "fate": "失踪"},
            "secret": "掌握封印碎片坐标",
            "romance_hook": "并肩作战后回头等你的人",
        },
    }


def test_opening_story_service_llm_success() -> None:
    settings = Settings()
    service = OpeningStoryService(settings=settings, provider=JsonProvider())
    result = service.generate_opening_story(
        world_profile=_world_profile(),
        player_profile=_player_profile(),
        backstory=_player_profile()["backstory"],
        first_chapter=_world_profile()["story_blueprint"]["acts"][0]["chapters"][0],
        story_enhancement=_world_profile()["story_enhancement"],
    )

    assert result.source == "llm"
    assert len(result.profile_digest_lines) >= 3
    assert "誓言" in result.backstory_scene
    assert "当前目标" in result.transition_line


def test_opening_story_service_fallback_on_invalid_json() -> None:
    settings = Settings()
    service = OpeningStoryService(settings=settings, provider=BrokenProvider())
    result = service.generate_opening_story(
        world_profile=_world_profile(),
        player_profile=_player_profile(),
        backstory=_player_profile()["backstory"],
        first_chapter=_world_profile()["story_blueprint"]["acts"][0]["chapters"][0],
        story_enhancement=_world_profile()["story_enhancement"],
    )

    assert result.source == "fallback"
    assert result.backstory_scene


def test_opening_intro_contains_story_and_no_inline_options_block() -> None:
    story = StorySession(
        user_id=uuid.uuid4(),
        title="demo",
        world_profile=_world_profile(),
        player_profile=_player_profile(),
        starter_options=[
            {"name_zh": "敲音猴"},
            {"name_zh": "呆火鳄"},
            {"name_zh": "呱呱泡蛙"},
        ],
    )
    opening_story = {
        "profile_digest_lines": ["名字：唐雨", "性格：外冷内热", "背景：边境幸存者"],
        "backstory_scene": "你在野星谷醒来，旧日灾变再次回响。",
        "transition_line": "当前目标：完成启程并锁定第一枚徽章线索。",
    }
    intro_text, action_options, _ = _opening_intro(story, opening_story=opening_story)

    assert "【主角档案摘要】" in intro_text
    assert "【前史回放】" in intro_text
    assert "【当前目标】" in intro_text
    assert "【可选动作】" not in intro_text
    assert len(action_options) >= 4
