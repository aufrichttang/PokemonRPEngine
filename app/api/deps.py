from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import RateLimiter
from app.core.security import SecurityService
from app.db.models import User
from app.db.session import get_db
from app.memory.schemas import EmbeddingProvider, get_embedding_provider
from app.providers.base import LLMProvider
from app.providers.mock import MockProvider
from app.providers.xfyun_http import XfyunHttpProvider
from app.providers.xfyun_ws import XfyunWsProvider
from app.services.admin_service import AdminService
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.session_service import SessionService

bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_security_service() -> SecurityService:
    return SecurityService(get_settings())


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_settings())


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "xfyun_http":
        return XfyunHttpProvider(settings)
    if settings.llm_provider == "xfyun_ws":
        return XfyunWsProvider(settings)
    return MockProvider()


@lru_cache(maxsize=1)
def get_embed_provider() -> EmbeddingProvider:
    settings = get_settings()
    return get_embedding_provider(settings.embedding_provider, dim=settings.embedding_dim)


def get_auth_service(
    security: Annotated[SecurityService, Depends(get_security_service)],
) -> AuthService:
    return AuthService(security)


def get_session_service() -> SessionService:
    return SessionService()


def get_chat_service() -> ChatService:
    settings = get_settings()
    return ChatService(
        settings=settings,
        provider=get_llm_provider(),
        embedding_provider=get_embed_provider(),
    )


def get_admin_service() -> AdminService:
    return AdminService()


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
    security: Annotated[SecurityService, Depends(get_security_service)],
) -> User:
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization"
        )
    try:
        payload = security.decode_token(creds.credentials)
        sub = payload.get("sub")
        user_id = uuid.UUID(str(sub))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_roles(*roles: str):
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role.value not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user

    return dependency


def enforce_rate_limit(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    key = f"{user.id}:{request.url.path}"
    if not limiter.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
        )
