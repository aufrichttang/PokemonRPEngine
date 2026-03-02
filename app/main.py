from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api.routers import admin, auth, canon, chat, health, metrics, sessions
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler, generic_error_handler
from app.core.logging import configure_logging, get_logger
from app.core.metrics import rp_requests_total
from app.core.security import SecurityService
from app.core.tracing import tracing_middleware
from app.db.session import SessionLocal
from app.services.auth_service import AuthService

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

app = FastAPI(title="Pokemon RP Engine", version="0.1.0")
origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    return await tracing_middleware(request, call_next)


@app.middleware("http")
async def metrics_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    rp_requests_total.labels(
        path=request.url.path,
        method=request.method,
        status=str(response.status_code),
    ).inc()
    return response


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(canon.router)
app.include_router(health.router)
app.include_router(metrics.router)


@app.on_event("startup")
def bootstrap_default_admin() -> None:
    logger.info(
        "app_startup",
        app_name=settings.app_name,
        provider=settings.llm_provider,
        database_url=settings.database_url.split("://")[0],
    )
    if not settings.bootstrap_default_admin:
        return
    try:
        security = SecurityService(settings)
        auth_service = AuthService(security)
        with SessionLocal() as db:
            created = auth_service.ensure_default_admin(
                db,
                username=settings.default_admin_username,
                password=settings.default_admin_password,
            )
        if created:
            logger.warning("default_admin_created", username=settings.default_admin_username)
    except SQLAlchemyError:
        logger.warning("default_admin_bootstrap_skipped")


@app.get("/")
def root() -> dict[str, str]:
    logger.info("root_called")
    return {"name": "pokemon-rp-engine", "status": "ok"}
