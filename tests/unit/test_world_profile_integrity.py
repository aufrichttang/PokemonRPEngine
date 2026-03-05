from __future__ import annotations

import uuid

from app.core.config import Settings
from app.db.models import Session as StorySession
from app.db.models import User, UserRole
from app.services.session_service import SessionService


def _create_user(db_session, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash="x",
        role=UserRole.admin,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_world_profile_integrity_backfills_legacy_session(db_session) -> None:
    user = _create_user(db_session, "legacy-map@test.com")
    session = StorySession(
        user_id=user.id,
        title="legacy",
        world_seed="legacy-seed-001",
        canon_gen=9,
        canon_game="sv",
        world_profile={"continent_name": "旧大陆"},
        player_profile={"name": "测试玩家", "backstory": {"origin": "旧存档"}},
        starter_options=[],
        gym_plan=[],
        player_state={"location": ""},
        battle_mode="fast",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    service = SessionService(settings=Settings(), provider=None)
    result = service.ensure_world_profile_integrity(db_session, session_obj=session, save=False)

    assert result["changed"] is True
    assert isinstance(session.world_profile, dict)
    assert session.world_profile.get("version") == 2
    assert "map_data" not in session.world_profile
    assert isinstance(session.player_state, dict)
    assert isinstance(session.player_state.get("story_progress"), dict)


def test_world_profile_integrity_keeps_healthy_session_stable(db_session) -> None:
    user = _create_user(db_session, "healthy-map@test.com")
    service = SessionService(settings=Settings(), provider=None)
    created = service.create_session(
        db_session,
        user_id=user.id,
        title="healthy",
        world_template_id=None,
        world_seed="stable-seed-001",
        canon_gen=9,
        canon_game="sv",
        custom_lore_enabled=False,
        player_profile={"name": "唐雨"},
    )

    result = service.ensure_world_profile_integrity(db_session, session_obj=created, save=False)

    assert result["changed"] is False
    assert isinstance(created.world_profile, dict)
    assert "map_data" not in created.world_profile
