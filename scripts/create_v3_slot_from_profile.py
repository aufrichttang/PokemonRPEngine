from __future__ import annotations

import argparse
import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Session as StorySession
from app.db.models import User
from app.db.session import SessionLocal
from app.services.session_service import SessionService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a new V3 slot/session from an existing player profile."
    )
    parser.add_argument("--user", required=True, help="username/email")
    parser.add_argument("--title", default="V3 新冒险", help="new session title")
    parser.add_argument("--seed", default=None, help="world seed")
    parser.add_argument("--canon-gen", type=int, default=9)
    parser.add_argument("--canon-game", default="sv")
    parser.add_argument("--from-session-id", default=None, help="source session id for profile cloning")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == args.user)).scalar_one_or_none()
        if user is None:
            raise SystemExit(f"user not found: {args.user}")

        profile = None
        if args.from_session_id:
            src = db.execute(
                select(StorySession).where(StorySession.id == uuid.UUID(args.from_session_id))
            ).scalar_one_or_none()
            if src is None:
                raise SystemExit(f"source session not found: {args.from_session_id}")
            profile = src.player_profile if isinstance(src.player_profile, dict) else None

        service = SessionService(settings=get_settings(), provider=None)
        story = service.create_session(
            db,
            user_id=user.id,
            title=args.title,
            world_template_id=None,
            world_seed=args.seed,
            canon_gen=args.canon_gen,
            canon_game=args.canon_game,
            custom_lore_enabled=False,
            player_profile=profile,
            ensure_v3_slot=True,
        )
        print(f"created session={story.id} world_seed={story.world_seed}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

