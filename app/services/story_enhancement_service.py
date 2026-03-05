from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.providers.base import LLMProvider

logger = get_logger(__name__)


class StoryEnhancementService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self._cache: dict[str, dict[str, Any]] = {}

    def _cache_key(
        self,
        *,
        seed: str,
        canon_gen: int,
        player_profile: dict[str, Any],
    ) -> str:
        profile_json = json.dumps(player_profile, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(profile_json.encode("utf-8")).hexdigest()[:16]
        return f"{seed}|{canon_gen}|{digest}"

    @staticmethod
    def default_story_enhancement(
        *,
        world_profile: dict[str, Any],
        player_profile: dict[str, Any],
    ) -> dict[str, Any]:
        story_blueprint = (
            world_profile.get("story_blueprint", {})
            if isinstance(world_profile.get("story_blueprint"), dict)
            else {}
        )
        chapter_beats: list[dict[str, Any]] = []
        acts = story_blueprint.get("acts", []) if isinstance(story_blueprint.get("acts"), list) else []
        for act in acts:
            if not isinstance(act, dict):
                continue
            for chapter in act.get("chapters", []):
                if not isinstance(chapter, dict):
                    continue
                chapter_beats.append(
                    {
                        "chapter": int(chapter.get("chapter_index", len(chapter_beats) + 1) or 1),
                        "hook": str(chapter.get("objective", "")).strip(),
                        "emotional_payoff": str(chapter.get("reward", "")).strip(),
                        "sacrifice": str(chapter.get("sacrifice_cost", "")).strip(),
                    }
                )
        if not chapter_beats:
            chapter_beats = [
                {
                    "chapter": 1,
                    "hook": "推进主线并锁定危机源头。",
                    "emotional_payoff": "建立伙伴羁绊并获得第一枚关键线索。",
                    "sacrifice": "必须放弃安稳与退路。",
                }
            ]

        romance_candidates = [
            c for c in (world_profile.get("romance_candidates") or []) if isinstance(c, dict)
        ]
        romance_hooks = [
            f"{c.get('name', '关键角色')}：{c.get('trait', '与主线纠缠的关键羁绊')}"
            for c in romance_candidates[:3]
        ]
        if not romance_hooks:
            romance_hooks = ["在主线推进中与关键角色建立高风险高回报的情感羁绊。"]

        backstory = (
            player_profile.get("backstory", {})
            if isinstance(player_profile.get("backstory"), dict)
            else {}
        )

        return {
            "arc_overview": (
                f"你将在{world_profile.get('continent_name', '未知大陆')}经历三幕八章主线，"
                "在恋爱抉择与多神兽危机中完成成长。"
            ),
            "chapter_beats": chapter_beats[:8],
            "legendary_conflict_dialogue_tone": "日漫轻小说风格，热血悲壮，保持紧凑节奏。",
            "romance_branch_hooks": romance_hooks,
            "backstory_polish": {
                "inciting_incident": str(backstory.get("inciting_incident", "神兽异象触发命运转折。")),
                "scar_and_vow": str(backstory.get("scar_and_vow", "以牺牲换取新秩序。")),
                "secret": str(backstory.get("secret", "你掌握足以改写终局的秘密。")),
            },
            "source": "fallback",
            "generated_with_llm": False,
        }

    @staticmethod
    def _extract_json_payload(text: str) -> dict[str, Any] | None:
        if not text:
            return None
        segments: list[str] = []
        if "<!--JSON-->" in text and "<!--/JSON-->" in text:
            start = text.find("<!--JSON-->") + len("<!--JSON-->")
            end = text.find("<!--/JSON-->", start)
            if end > start:
                segments.append(text[start:end].strip())
        if "```json" in text:
            start = text.find("```json") + len("```json")
            end = text.find("```", start)
            if end > start:
                segments.append(text[start:end].strip())
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}")
            if end > start:
                segments.append(text[start : end + 1].strip())

        for candidate in segments:
            try:
                payload = json.loads(candidate)
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
    ) -> list[dict[str, str]]:
        brief = {
            "continent_name": world_profile.get("continent_name"),
            "theme_tags": world_profile.get("theme_tags"),
            "start_town": world_profile.get("start_town"),
            "story_blueprint": world_profile.get("story_blueprint"),
            "legendary_web": world_profile.get("legendary_web"),
            "romance_candidates": world_profile.get("romance_candidates"),
            "player_profile": {
                "name": player_profile.get("name"),
                "gender": player_profile.get("gender"),
                "personality": player_profile.get("personality"),
                "background": player_profile.get("background"),
                "detail": player_profile.get("detail"),
                "backstory": player_profile.get("backstory"),
            },
        }
        prompt = (
            "你是宝可梦世界剧情总监。请在不破坏三幕八章骨架的前提下，"
            "输出更有情绪张力的主线润色包。"
            "要求：中文、热血悲壮、轻小说节奏、可直接用于游戏。\n"
            "只输出 JSON，不要解释。\n"
            "JSON schema:\n"
            "{"
            '"arc_overview": "string",'
            '"chapter_beats":[{"chapter":1,"hook":"...","emotional_payoff":"...","sacrifice":"..."}],'
            '"legendary_conflict_dialogue_tone":"string",'
            '"romance_branch_hooks":["..."],'
            '"backstory_polish":{"inciting_incident":"...","scar_and_vow":"...","secret":"..."}'
            "}\n"
            f"输入资料：{json.dumps(brief, ensure_ascii=False)}"
        )
        return [
            {"role": "system", "content": "你必须严格输出合法 JSON 对象。"},
            {"role": "user", "content": prompt},
        ]

    def enhance_story(
        self,
        *,
        world_profile: dict[str, Any],
        player_profile: dict[str, Any],
        seed: str,
        canon_gen: int,
    ) -> dict[str, Any]:
        fallback = self.default_story_enhancement(
            world_profile=world_profile,
            player_profile=player_profile,
        )
        cache_key = self._cache_key(
            seed=seed,
            canon_gen=canon_gen,
            player_profile=player_profile,
        )
        if cache_key in self._cache:
            cached = dict(self._cache[cache_key])
            cached["cache_hit"] = True
            return cached

        settings = self.settings
        provider = self.provider
        if not settings or not provider or not settings.story_enhancement_enabled:
            fallback["reason"] = "disabled_or_missing_provider"
            fallback["cache_hit"] = False
            self._cache[cache_key] = dict(fallback)
            return fallback

        started = datetime.now(UTC)
        timeout_seconds = max(1, int(settings.story_enhancement_timeout_seconds))
        prompt_messages = self._build_prompt(
            world_profile=world_profile,
            player_profile=player_profile,
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
                raise ValueError("invalid_story_enhancement_json")
            required_any = {"arc_overview", "chapter_beats", "backstory_polish"}
            if not required_any.intersection(payload.keys()):
                raise ValueError("story_enhancement_keys_missing")

            merged = dict(fallback)
            merged.update(
                {
                    "arc_overview": str(payload.get("arc_overview") or merged["arc_overview"]),
                    "chapter_beats": payload.get("chapter_beats") or merged["chapter_beats"],
                    "legendary_conflict_dialogue_tone": str(
                        payload.get("legendary_conflict_dialogue_tone")
                        or merged["legendary_conflict_dialogue_tone"]
                    ),
                    "romance_branch_hooks": payload.get("romance_branch_hooks")
                    or merged["romance_branch_hooks"],
                    "backstory_polish": payload.get("backstory_polish")
                    or merged["backstory_polish"],
                    "source": "llm",
                    "generated_with_llm": True,
                    "cache_hit": False,
                    "generated_at": started.isoformat(),
                }
            )
            self._cache[cache_key] = dict(merged)
            return merged
        except Exception as exc:
            logger.warning(
                "story_enhancement_fallback",
                reason=str(exc),
                seed=seed,
                canon_gen=canon_gen,
            )
            fallback["reason"] = str(exc)
            fallback["cache_hit"] = False
            fallback["generated_at"] = started.isoformat()
            self._cache[cache_key] = dict(fallback)
            return fallback
