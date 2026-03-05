import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.core.config import get_settings
from app.core.logging import get_logger, trace_id_var

logger = get_logger(__name__)
settings = get_settings()


async def tracing_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
    token = trace_id_var.set(trace_id)
    request.state.trace_id = trace_id

    start = time.perf_counter()
    if settings.request_log_enabled:
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )

    try:
        response = await call_next(request)
    finally:
        trace_id_var.reset(token)

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    response.headers["X-Trace-Id"] = trace_id
    response.headers["X-Process-Time-Ms"] = str(elapsed_ms)

    if settings.request_log_enabled:
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=elapsed_ms,
            slow=elapsed_ms >= settings.slow_request_ms,
        )

    return response
