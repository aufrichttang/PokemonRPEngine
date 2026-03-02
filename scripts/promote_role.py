from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db.models import User, UserRole
from app.db.session import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote an existing user role.")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument(
        "--role",
        required=True,
        choices=[r.value for r in UserRole if r.value != "user"] + ["user"],
        help="Target role",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == args.email)).scalar_one_or_none()
        if not user:
            print(f"user not found: {args.email}")
            return 1
        user.role = UserRole(args.role)
        db.add(user)
        db.commit()
        print(f"updated {args.email} -> role={user.role.value}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
