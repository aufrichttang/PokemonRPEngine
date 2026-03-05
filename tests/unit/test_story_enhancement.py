from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import delete

from app.core.config import Settings
from app.db.models import CanonPokemon, User, UserRole
from app.providers.base import LLMProvider
from app.services.session_service import SessionService


class BrokenProvider(LLMProvider):
    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool,
        json_mode: bool = False,
        **params: Any,
    ) -> str | AsyncIterator[str]:
        raise RuntimeError("provider unavailable")


def _seed_pokemon(db_session) -> None:
    db_session.execute(delete(CanonPokemon))
    db_session.add_all(
        [
            CanonPokemon(
                dex_no=1,
                slug_id="bulbasaur",
                name_zh="妙蛙种子",
                name_en="Bulbasaur",
                aliases=["bulbasaur", "妙蛙种子"],
                form=None,
                types=["grass", "poison"],
                base_stats={},
                abilities=["overgrow"],
                generation=1,
                source="test",
                source_version="v1",
            ),
            CanonPokemon(
                dex_no=4,
                slug_id="charmander",
                name_zh="小火龙",
                name_en="Charmander",
                aliases=["charmander", "小火龙"],
                form=None,
                types=["fire"],
                base_stats={},
                abilities=["blaze"],
                generation=1,
                source="test",
                source_version="v1",
            ),
            CanonPokemon(
                dex_no=7,
                slug_id="squirtle",
                name_zh="杰尼龟",
                name_en="Squirtle",
                aliases=["squirtle", "杰尼龟"],
                form=None,
                types=["water"],
                base_stats={},
                abilities=["torrent"],
                generation=1,
                source="test",
                source_version="v1",
            ),
        ]
    )
    db_session.commit()


def test_story_enhancement_fallback_on_provider_failure(db_session) -> None:
    _seed_pokemon(db_session)
    user_id = uuid.uuid4()
    db_session.add(
        User(
            id=user_id,
            email="story-fallback@test.com",
            password_hash="x",
            role=UserRole.admin,
        )
    )
    db_session.commit()

    settings = Settings()
    settings.story_enhancement_enabled = True
    settings.story_enhancement_timeout_seconds = 1

    service = SessionService(settings=settings, provider=BrokenProvider())
    session = service.create_session(
        db_session,
        user_id=user_id,
        title="enhance fallback",
        world_template_id=None,
        world_seed="fallback-seed",
        canon_gen=9,
        canon_game="sv",
        custom_lore_enabled=False,
        player_profile={"name": "唐雨"},
    )

    world_profile = session.world_profile or {}
    player_profile = session.player_profile or {}
    enhancement = world_profile.get("story_enhancement", {})
    backstory = player_profile.get("backstory", {}) if isinstance(player_profile, dict) else {}

    assert enhancement.get("source") == "fallback"
    assert isinstance(enhancement.get("chapter_beats"), list)
    assert isinstance(backstory.get("enhanced"), dict)
