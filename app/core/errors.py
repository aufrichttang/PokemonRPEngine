from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AppError(Exception):
    code: str
    message: str
    status_code: int = HTTPStatus.BAD_REQUEST
    details: dict[str, Any] | None = None


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", "-")
    logger.warning(
        "app_error",
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        path=request.url.path,
    )

    payload: dict[str, Any] = {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "trace_id": trace_id,
        }
    }
    if exc.details:
        payload["error"]["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=payload)


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", "-")
    logger.exception("internal_error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": str(exc), "trace_id": trace_id}},
    )
