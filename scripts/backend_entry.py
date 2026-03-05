from __future__ import annotations

import os

import uvicorn

from app.db.base import Base
from app.db.session import engine
from app.main import app


def ensure_db() -> None:
    Base.metadata.create_all(bind=engine)


def main() -> None:
    os.environ.setdefault("APP_HOST", "127.0.0.1")
    os.environ.setdefault("APP_PORT", "8000")
    ensure_db()
    # Use direct app object to avoid module-string import issues in PyInstaller onefile mode.
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
