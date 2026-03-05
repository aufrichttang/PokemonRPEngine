from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import Settings


class SecurityService:
    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

    def create_token(self, subject: str, role: str) -> str:
        expires = datetime.now(tz=UTC) + timedelta(minutes=self.settings.jwt_expire_minutes)
        payload: dict[str, Any] = {"sub": subject, "role": role, "exp": expires}
        return jwt.encode(payload, self.settings.jwt_secret, algorithm=self.settings.jwt_algorithm)

    def decode_token(self, token: str) -> dict[str, Any]:
        return jwt.decode(token, self.settings.jwt_secret, algorithms=[self.settings.jwt_algorithm])
