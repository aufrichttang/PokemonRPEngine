from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.providers.base import LLMProvider

logger = get_logger(__name__)


@dataclass
class OpeningStoryResult:
    profile_digest_lines: list[str]
    backstory_scene: str
    transition_line: str
    source: str = "fallback"


class OpeningStoryService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider

    @staticmethod
    def _default_result(
        *,
        world_profile: dict[str, Any],
        player_profile: dict[str, Any],
        backstory: dict[str, Any],
        first_chapter: dict[str, Any],
    ) -> OpeningStoryResult:
        start_town = str(world_profile.get("start_town") or "未知城镇")
        continent_name = str(world_profile.get("continent_name") or "未知大陆")
        profile_digest = [
            f"名字：{player_profile.get('name', '未命名')}，{player_profile.get('gender', '未知')}，{player_profile.get('age', '?')}岁，{player_profile.get('height_cm', '?')}cm。",
            f"外形：{player_profile.get('appearance', '轮廓清晰，神情克制')}。",
            f"性格：{player_profile.get('personality', '外冷内热，关键时刻会挺身而出')}。",
            f"背景：{player_profile.get('background', '来自边境地带，经历过重大异象')}。",
            f"执念：{backstory.get('scar_and_vow', '不再让同伴独自承担代价')}。",
        ]
        scene = (
            f"夜色压在{start_town}的矿轨上，风里带着盐与机油的味道。你从碎石坡醒来，"
            f"掌心的金属碎片仍然发烫。远处，{continent_name}上空的遗迹投影忽明忽暗，像一只缓慢睁开的眼。\n\n"
            f"你想起那场改变命运的事件：{backstory.get('inciting_incident', '神兽异象撕裂了平静的夜晚')}。"
            "当时你没能救下所有人，旧羁绊也在混乱里断裂。"
            f"{backstory.get('past_companion', {}).get('name', '那位旧友')}留下最后线索后失踪，"
            "只剩一句未说完的警告。\n\n"
            f"你把秘密压在心底：{backstory.get('secret', '你掌握足以改写终局的关键坐标')}。"
            "现在警报再次响起，你明白自己已经没有退路。"
        )
        transition = (
            f"当前目标：{first_chapter.get('objective', '完成启程并锁定第一枚徽章线索')}。"
            f"代价预警：{first_chapter.get('sacrifice_cost', '胜利伴随牺牲')}。"
        )
        return OpeningStoryResult(
            profile_digest_lines=profile_digest[:5],
            backstory_scene=scene,
            transition_line=transition,
            source="fallback",
        )

    @staticmethod
    def _extract_json_payload(text: str) -> dict[str, Any] | None:
        if not text:
            return None

        candidates: list[str] = []
        if "<!--JSON-->" in text and "<!--/JSON-->" in text:
            start = text.find("<!--JSON-->") + len("<!--JSON-->")
            end = text.find("<!--/JSON-->", start)
            if end > start:
                candidates.append(text[start:end].strip())
        if "```json" in text:
            start = text.find("```json") + len("```json")
            end = text.find("```", start)
            if end > start:
                candidates.append(text[start:end].strip())
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}")
            if end > start:
                candidates.append(text[start : end + 1].strip())

        for raw in candidates:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return None

    @staticmethod
    def _build_prompt(
        *,
        world_profile: dict[str, Any],
        player_profile: dict[str, Any],
        backstory: dict[str, Any],
        first_chapter: dict[str, Any],
        story_enhancement: dict[str, Any],
    ) -> list[dict[str, str]]:
        brief = {
            "continent_name": world_profile.get("continent_name"),
            "start_town": world_profile.get("start_town"),
            "theme_tags": world_profile.get("theme_tags"),
            "player_profile": {
                "name": player_profile.get("name"),
                "gender": player_profile.get("gender"),
                "age": player_profile.get("age"),
                "height_cm": player_profile.get("height_cm"),
                "appearance": player_profile.get("appearance"),
                "personality": player_profile.get("personality"),
                "background": player_profile.get("background"),
                "detail": player_profile.get("detail"),
            },
            "backstory": backstory,
            "chapter_objective": first_chapter.get("objective"),
            "chapter_stakes": first_chapter.get("sacrifice_cost"),
            "arc_overview": story_enhancement.get("arc_overview"),
        }
        user_prompt = (
            "你是宝可梦JRPG叙事编辑。请根据输入生成“建角后开场文本”，输出严格 JSON。\n"
            "要求：\n"
            "1) profile_digest_lines: 3~5条，短句，人物摘要；\n"
            "2) backstory_scene: 400~700字，沉浸叙事，必须包含触发事件、创伤誓言、旧羁绊、隐藏秘密；\n"
            "3) transition_line: 1~2句，明确当前章节目标与代价；\n"
            "4) 文风自然，不要列表堆砌，不要编造脱离输入的设定。\n"
            "JSON schema:\n"
            "{"
            '"profile_digest_lines":["..."],'
            '"backstory_scene":"...",'
            '"transition_line":"..."'
            "}\n"
            f"输入资料：{json.dumps(brief, ensure_ascii=False)}"
        )
        return [
            {"role": "system", "content": "你只能输出合法 JSON，不要输出解释。"},
            {"role": "user", "content": user_prompt},
        ]

    def generate_opening_story(
        self,
        *,
        world_profile: dict[str, Any],
        player_profile: dict[str, Any],
        backstory: dict[str, Any],
        first_chapter: dict[str, Any],
        story_enhancement: dict[str, Any],
    ) -> OpeningStoryResult:
        fallback = self._default_result(
            world_profile=world_profile,
            player_profile=player_profile,
            backstory=backstory,
            first_chapter=first_chapter,
        )
        settings = self.settings
        provider = self.provider
        if not settings or not provider:
            return fallback

        timeout_seconds = max(3, int(settings.story_enhancement_timeout_seconds))
        prompt_messages = self._build_prompt(
            world_profile=world_profile,
            player_profile=player_profile,
            backstory=backstory,
            first_chapter=first_chapter,
            story_enhancement=story_enhancement,
        )

        try:
            async def _call_provider() -> str:
                result = await provider.generate(
                    prompt_messages,
                    stream=False,
                    json_mode=True,
                )
                return result if isinstance(result, str) else ""

            raw = asyncio.run(asyncio.wait_for(_call_provider(), timeout=timeout_seconds))
            payload = self._extract_json_payload(raw)
            if not isinstance(payload, dict):
                raise ValueError("invalid_opening_story_json")

            digest = payload.get("profile_digest_lines")
            scene = payload.get("backstory_scene")
            transition = payload.get("transition_line")
            if not isinstance(digest, list) or not digest:
                raise ValueError("opening_story_digest_missing")
            if not isinstance(scene, str) or not scene.strip():
                raise ValueError("opening_story_scene_missing")
            if not isinstance(transition, str) or not transition.strip():
                raise ValueError("opening_story_transition_missing")

            digest_lines = [str(item).strip() for item in digest if str(item).strip()]
            if not digest_lines:
                raise ValueError("opening_story_digest_empty")

            return OpeningStoryResult(
                profile_digest_lines=digest_lines[:5],
                backstory_scene=scene.strip(),
                transition_line=transition.strip(),
                source="llm",
            )
        except Exception as exc:
            logger.warning("opening_story_fallback", reason=str(exc))
            return fallback
