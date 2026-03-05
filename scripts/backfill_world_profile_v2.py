from __future__ import annotations

import argparse
import uuid

from sqlalchemy import desc, select

from app.core.config import get_settings
from app.db.models import Session as StorySession
from app.db.session import SessionLocal
from app.services.session_service import SessionService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill legacy sessions to world_profile version=2 with map/story integrity.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print planned changes.")
    parser.add_argument("--limit", type=int, default=0, help="Max sessions to process. 0 means all.")
    parser.add_argument("--session-id", type=str, default="", help="Only process one session UUID.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    service = SessionService(settings=settings, provider=None)

    processed = 0
    changed = 0
    with SessionLocal() as db:
        stmt = select(StorySession).where(StorySession.deleted.is_(False)).order_by(
            desc(StorySession.updated_at)
        )
        if args.session_id:
            stmt = stmt.where(StorySession.id == uuid.UUID(args.session_id))
        if args.limit and args.limit > 0:
            stmt = stmt.limit(args.limit)

        sessions = list(db.execute(stmt).scalars().all())
        total = len(sessions)
        print(f"[backfill] scanning sessions: {total}")

        for sess in sessions:
            processed += 1
            result = service.ensure_world_profile_integrity(
                db,
                session_obj=sess,
                save=not args.dry_run,
            )
            if bool(result.get("changed")):
                changed += 1
                fields = ",".join(result.get("changed_fields", []))
                print(f"[changed] {sess.id} fields={fields}")
            else:
                print(f"[ok] {sess.id} already healthy")

        if args.dry_run:
            db.rollback()
            print("[backfill] dry-run mode, rolled back.")

    print(f"[backfill] done processed={processed} changed={changed} dry_run={args.dry_run}")


if __name__ == "__main__":
    main()
