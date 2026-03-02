from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.deps import require_roles
from app.core.config import get_settings
from app.core.metrics import snapshot_summary
from app.db.models import User

router = APIRouter(tags=["metrics"])
settings = get_settings()


@router.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/v1/admin/metrics")
def admin_metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/v1/admin/metrics/summary")
def admin_metrics_summary(
    _user: Annotated[User, Depends(require_roles("admin", "operator"))],
) -> dict[str, float]:
    return snapshot_summary()


@router.get("/v1/admin/logs/recent")
def admin_recent_logs(
    _user: Annotated[User, Depends(require_roles("admin", "operator"))],
    lines: int = Query(default=200, ge=10, le=5000),
) -> dict[str, object]:
    log_path = Path(settings.log_file_path)
    if not log_path.exists():
        return {"path": str(log_path), "lines": []}
    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        tail = list(deque(f, maxlen=lines))
    return {"path": str(log_path), "lines": [line.rstrip("\n") for line in tail]}
