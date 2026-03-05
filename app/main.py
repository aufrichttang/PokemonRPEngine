from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.api.routers import game_v2, health, metrics
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler, generic_error_handler
from app.core.logging import configure_logging, get_logger
from app.core.metrics import rp_requests_total
from app.core.security import SecurityService
from app.core.tracing import tracing_middleware
from app.db.session import SessionLocal
from app.db.session import engine as db_engine
from app.services.auth_service import AuthService

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
def bootstrap_default_admin() -> None:
    logger.info(
        "app_startup",
        app_name=settings.app_name,
        provider=settings.llm_provider,
        model_id=settings.xf_model_id,
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

    try:
        with db_engine.begin() as conn:
            inspector = inspect(conn)
            session_cols = {c["name"] for c in inspector.get_columns("sessions")}
            if "player_profile" not in session_cols:
                conn.execute(text("ALTER TABLE sessions ADD COLUMN player_profile JSON"))
                logger.warning("runtime_schema_updated", table="sessions", column="player_profile")
    except SQLAlchemyError:
        logger.warning("runtime_schema_update_skipped")


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap_default_admin()
    yield


app = FastAPI(title="Pokemon RP Engine", version="0.1.0", lifespan=lifespan)
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

app.include_router(game_v2.router)
app.include_router(health.router)
app.include_router(metrics.router)


@app.get("/")
def root() -> dict[str, str]:
    logger.info("root_called")
    return {"name": "pokemon-rp-engine", "status": "ok"}
