from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Session as StorySession
from app.worldgen.generator import generate_world

from .story_enhancement_service import StoryEnhancementService

logger = get_logger(__name__)


@dataclass
class IntegrityResult:
    world_profile: dict[str, Any]
    player_profile: dict[str, Any]
    changed: bool
    changed_fields: list[str]
    migration_applied: bool


class SessionWorldService:
    def __init__(self, story_enhancement: StoryEnhancementService) -> None:
        self.story_enhancement = story_enhancement

    def ensure_world_profile_integrity(
        self,
        db: Session,
        *,
        session_obj: StorySession,
        save: bool = True,
    ) -> IntegrityResult:
        world_profile = (
            dict(session_obj.world_profile)
            if isinstance(session_obj.world_profile, dict)
            else {}
        )
        player_profile = (
            dict(session_obj.player_profile)
            if isinstance(session_obj.player_profile, dict)
            else {}
        )
        changed_fields: list[str] = []
        generated_cache: dict[str, Any] | None = None

        def _generated_world() -> dict[str, Any]:
            nonlocal generated_cache
            if generated_cache is None:
                generated = generate_world(
                    db,
                    seed=session_obj.world_seed,
                    canon_gen=session_obj.canon_gen,
                    canon_game=session_obj.canon_game,
                )
                generated_cache = {
                    "seed": generated.seed,
                    "world_profile": generated.world_profile,
                    "starter_options": generated.starter_options,
                    "gym_plan": generated.gym_plan,
                    "battle_mode": generated.battle_mode,
                }
            return generated_cache

        # Base version marker for future migrations.
        if int(world_profile.get("version", 0) or 0) < 2:
            world_profile["version"] = 2
            changed_fields.append("world_profile.version")

        # Keep world seed mirrored in profile for deterministic replay.
        if not world_profile.get("seed"):
            seed = session_obj.world_seed or str(_generated_world()["seed"])
            world_profile["seed"] = seed
            changed_fields.append("world_profile.seed")

        # Ensure essential world fields exist.
        for key in (
            "continent_name",
            "theme_tags",
            "start_town",
            "story_blueprint",
            "legendary_web",
            "sacrifice_stakes",
            "legendary_arc",
        ):
            if key not in world_profile or world_profile.get(key) in (None, "", [], {}):
                world_profile[key] = _generated_world()["world_profile"].get(key)
                changed_fields.append(f"world_profile.{key}")

        # Ensure starter/gym payloads for old sessions.
        if not isinstance(session_obj.starter_options, list) or not session_obj.starter_options:
            session_obj.starter_options = _generated_world()["starter_options"]
            changed_fields.append("session.starter_options")
        if not isinstance(session_obj.gym_plan, list) or not session_obj.gym_plan:
            session_obj.gym_plan = _generated_world()["gym_plan"]
            changed_fields.append("session.gym_plan")
        if not session_obj.battle_mode:
            session_obj.battle_mode = str(_generated_world()["battle_mode"] or "fast")
            changed_fields.append("session.battle_mode")

        # Story enhancement is needed by the game HUD and opening flavor.
        enhancement = world_profile.get("story_enhancement")
        if not isinstance(enhancement, dict) or not enhancement.get("arc_overview"):
            fallback = self.story_enhancement.default_story_enhancement(
                world_profile=world_profile,
                player_profile=player_profile,
            )
            fallback["source"] = "migrated_fallback"
            world_profile["story_enhancement"] = fallback
            changed_fields.append("world_profile.story_enhancement")
        else:
            world_profile["story_enhancement"] = enhancement

        # Ensure player backstory enhancement block.
        if isinstance(player_profile.get("backstory"), dict):
            backstory = dict(player_profile["backstory"])
            enhanced = backstory.get("enhanced")
            if not isinstance(enhanced, dict):
                polish = (
                    world_profile.get("story_enhancement", {}).get("backstory_polish", {})
                    if isinstance(world_profile.get("story_enhancement"), dict)
                    else {}
                )
                backstory["enhanced"] = polish if isinstance(polish, dict) else {}
                player_profile["backstory"] = backstory
                changed_fields.append("player_profile.backstory.enhanced")

        # Ensure minimal player story progress to sync map/hud.
        player_state = dict(session_obj.player_state) if isinstance(session_obj.player_state, dict) else {}
        if not isinstance(player_state.get("story_progress"), dict):
            story_blueprint = (
                world_profile.get("story_blueprint", {})
                if isinstance(world_profile.get("story_blueprint"), dict)
                else {}
            )
            first_objective = "完成启程并锁定主线危机"
            acts = story_blueprint.get("acts", []) if isinstance(story_blueprint.get("acts"), list) else []
            if acts and isinstance(acts[0], dict):
                chapters = acts[0].get("chapters", [])
                if chapters and isinstance(chapters[0], dict):
                    first_objective = str(chapters[0].get("objective") or first_objective)
            player_state["story_progress"] = {
                "act": 1,
                "chapter": 1,
                "objective": first_objective,
                "objective_status": "pending",
                "turns_in_chapter": 0,
            }
            changed_fields.append("player_state.story_progress")

        if not player_state.get("location"):
            player_state["location"] = str(
                world_profile.get("start_town")
                or ""
            )
            changed_fields.append("player_state.location")

        migration_applied = len(changed_fields) > 0
        if migration_applied:
            session_obj.world_profile = world_profile
            session_obj.player_profile = player_profile
            session_obj.player_state = player_state
            session_obj.updated_at = datetime.now(UTC)
            if save:
                db.add(session_obj)
                db.commit()
                db.refresh(session_obj)
            logger.info(
                "world_profile_integrity_migrated",
                session_id=str(session_obj.id),
                changed_fields=changed_fields,
            )
        return IntegrityResult(
            world_profile=world_profile,
            player_profile=player_profile,
            changed=migration_applied,
            changed_fields=changed_fields,
            migration_applied=migration_applied,
        )
