from __future__ import annotations

from typing import Any

from app.db.models import Session as StorySession


class StoryProgressService:
    @staticmethod
    def _chapter_lookup(world_profile: dict[str, Any]) -> dict[int, dict[str, Any]]:
        lookup: dict[int, dict[str, Any]] = {}
        story_blueprint = (
            world_profile.get("story_blueprint", {})
            if isinstance(world_profile.get("story_blueprint"), dict)
            else {}
        )
        acts = story_blueprint.get("acts", []) if isinstance(story_blueprint.get("acts"), list) else []
        for act in acts:
            if not isinstance(act, dict):
                continue
            for chapter in act.get("chapters", []):
                if not isinstance(chapter, dict):
                    continue
                idx = int(chapter.get("chapter_index", 0) or 0)
                if idx > 0:
                    lookup[idx] = chapter
        return lookup

    def apply_story_progress(
        self,
        *,
        session_obj: StorySession,
        merged_state: dict[str, Any],
        user_text: str,
        assistant_text: str,
    ) -> dict[str, Any]:
        world_profile = (
            dict(session_obj.world_profile)
            if isinstance(session_obj.world_profile, dict)
            else {}
        )
        chapter_lookup = self._chapter_lookup(world_profile)
        if not chapter_lookup:
            return merged_state

        progress = (
            merged_state.get("story_progress", {})
            if isinstance(merged_state.get("story_progress"), dict)
            else {}
        )
        current_chapter = int(progress.get("chapter", 1) or 1)
        current_act = int(progress.get("act", 1) or 1)
        turns_in_chapter = int(progress.get("turns_in_chapter", 0) or 0) + 1
        objective_status = str(progress.get("objective_status", "pending") or "pending")

        joined_text = f"{user_text}\n{assistant_text}"
        complete_markers = (
            "完成",
            "通关",
            "击败",
            "封印",
            "救下",
            "成功",
            "达成",
            "夺回",
            "觉醒",
            "牺牲",
            "抉择",
        )
        should_advance = turns_in_chapter >= 3 or any(marker in joined_text for marker in complete_markers)
        if should_advance:
            objective_status = "completed"
            chapter = chapter_lookup.get(current_chapter)
            if isinstance(chapter, dict):
                chapter["status"] = "completed"
            if current_chapter < max(chapter_lookup.keys()):
                current_chapter += 1
                next_chapter = chapter_lookup.get(current_chapter, {})
                if isinstance(next_chapter, dict):
                    next_chapter["status"] = "active"
                current_act = int(next_chapter.get("act_index", current_act) or current_act)
                progress["objective"] = str(next_chapter.get("objective", "")).strip()
                objective_status = "pending"
                turns_in_chapter = 0
            else:
                objective_status = "finale"
                turns_in_chapter = min(turns_in_chapter, 99)

        if not progress.get("objective"):
            chapter = chapter_lookup.get(current_chapter)
            if isinstance(chapter, dict):
                progress["objective"] = str(chapter.get("objective", "")).strip()

        progress["act"] = current_act
        progress["chapter"] = current_chapter
        progress["objective_status"] = objective_status
        progress["turns_in_chapter"] = turns_in_chapter

        merged_state["story_progress"] = progress
        merged_state["current_chapter_objective"] = progress.get("objective", "")

        quests = merged_state.get("quests", [])
        if not isinstance(quests, list):
            quests = []
        chapter_goal = progress.get("objective", "")
        quest_line = f"主线第{current_chapter}章：{chapter_goal}"
        quests = [q for q in quests if not (isinstance(q, str) and q.startswith("主线第"))]
        quests.append(quest_line)
        merged_state["quests"] = quests

        story_blueprint = world_profile.get("story_blueprint", {})
        if isinstance(story_blueprint, dict):
            story_blueprint["current_chapter"] = current_chapter
            story_blueprint["current_act"] = current_act
        world_profile["story_blueprint"] = story_blueprint

        if not merged_state.get("location"):
            merged_state["location"] = str(world_profile.get("start_town") or "")

        session_obj.world_profile = world_profile
        return merged_state
