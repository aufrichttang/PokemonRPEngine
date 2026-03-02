from __future__ import annotations

import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import CanonLevel, TimelineEvent, Turn
from app.db.models import Session as StorySession


class SessionService:
    def create_session(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        title: str,
        world_template_id: str | None,
        canon_gen: int,
        canon_game: str | None,
        custom_lore_enabled: bool,
    ) -> StorySession:
        story = StorySession(
            user_id=user_id,
            title=title,
            world_template_id=world_template_id,
            canon_gen=canon_gen,
            canon_game=canon_game,
            custom_lore_enabled=custom_lore_enabled,
        )
        db.add(story)
        db.commit()
        db.refresh(story)
        return story

    def list_sessions(
        self, db: Session, *, user_id: uuid.UUID, page: int, size: int
    ) -> list[StorySession]:
        stmt = (
            select(StorySession)
            .where(StorySession.user_id == user_id, StorySession.deleted.is_(False))
            .order_by(desc(StorySession.updated_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        return list(db.execute(stmt).scalars().all())

    def get_session(self, db: Session, *, session_id: uuid.UUID) -> StorySession | None:
        return db.execute(
            select(StorySession).where(
                StorySession.id == session_id, StorySession.deleted.is_(False)
            )
        ).scalar_one_or_none()

    def get_recent_turns(
        self, db: Session, *, session_id: uuid.UUID, limit: int = 50
    ) -> list[Turn]:
        stmt = (
            select(Turn)
            .where(Turn.session_id == session_id)
            .order_by(desc(Turn.turn_index))
            .limit(limit)
        )
        rows = list(db.execute(stmt).scalars().all())
        rows.reverse()
        return rows

    def delete_session(self, db: Session, *, session_id: uuid.UUID) -> None:
        session = db.execute(select(StorySession).where(StorySession.id == session_id)).scalar_one()
        session.deleted = True
        db.add(session)
        db.commit()

    def export_session(
        self,
        db: Session,
        *,
        session_id: uuid.UUID,
    ) -> dict:
        sess = db.execute(
            select(StorySession).where(
                StorySession.id == session_id, StorySession.deleted.is_(False)
            )
        ).scalar_one()
        turns = self.get_recent_turns(db, session_id=session_id, limit=10_000)
        return {
            "session": {
                "id": str(sess.id),
                "title": sess.title,
                "canon_gen": sess.canon_gen,
                "canon_game": sess.canon_game,
                "created_at": sess.created_at.isoformat() if sess.created_at else None,
                "updated_at": sess.updated_at.isoformat() if sess.updated_at else None,
            },
            "turns": [
                {
                    "turn_index": t.turn_index,
                    "user_text": t.user_text,
                    "assistant_text": t.assistant_text,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in turns
            ],
        }

    def list_timeline_events(
        self,
        db: Session,
        *,
        session_id: uuid.UUID,
        canon_level: CanonLevel | None,
        page: int,
        size: int,
    ) -> list[TimelineEvent]:
        stmt = (
            select(TimelineEvent)
            .where(TimelineEvent.session_id == session_id)
            .order_by(desc(TimelineEvent.created_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        if canon_level:
            stmt = stmt.where(TimelineEvent.canon_level == canon_level)
        return list(db.execute(stmt).scalars().all())
