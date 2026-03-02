from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.security import SecurityService
from app.db.models import User

logger = get_logger(__name__)


@dataclass
class AuthResult:
    access_token: str
    token_type: str = "bearer"


class AuthService:
    def __init__(self, security: SecurityService):
        self.security = security

    def register(self, db: Session, *, email: str, password: str, role: str = "user") -> User:
        exists = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if exists:
            raise AppError(code="email_exists", message="Email already registered", status_code=409)
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=self.security.hash_password(password),
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def ensure_default_admin(self, db: Session, *, username: str, password: str) -> bool:
        exists = db.execute(select(User).where(User.email == username)).scalar_one_or_none()
        if exists:
            return False
        user = User(
            id=uuid.uuid4(),
            email=username,
            password_hash=self.security.hash_password(password),
            role="admin",
        )
        db.add(user)
        db.commit()
        return True

    def login(self, db: Session, *, email: str, password: str) -> AuthResult:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not user or not self.security.verify_password(password, user.password_hash):
            logger.warning("login_failed", account=email)
            raise AppError(
                code="invalid_credentials", message="Invalid account or password", status_code=401
            )
        logger.info("login_success", user_id=str(user.id), role=user.role.value)
        token = self.security.create_token(str(user.id), user.role.value)
        return AuthResult(access_token=token)
