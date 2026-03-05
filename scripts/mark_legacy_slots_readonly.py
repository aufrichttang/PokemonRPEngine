from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db.models import SaveSlot
from app.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Mark V2 legacy slots as readonly/inactive.")
    parser.add_argument("--dry-run", action="store_true", help="Only print changes.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = db.execute(select(SaveSlot).where(SaveSlot.schema_version < 3)).scalars().all()
        print(f"legacy slots: {len(rows)}")
        for slot in rows:
            print(f"- slot={slot.id} session={slot.session_id} schema={slot.schema_version}")
            if not args.dry_run:
                slot.is_active = False
                db.add(slot)
        if not args.dry_run:
            db.commit()
            print("done: legacy slots marked inactive.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

