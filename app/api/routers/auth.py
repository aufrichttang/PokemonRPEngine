from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_auth_service
from app.db.session import get_db
from app.services.auth_service import AuthService

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str


@router.post("/register")
def register(
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict:
    user = auth_service.register(db, email=str(payload.email), password=payload.password)
    return {"id": str(user.id), "email": user.email, "role": user.role.value}


@router.post("/login")
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict:
    token = auth_service.login(db, email=str(payload.email), password=payload.password)
    return {"access_token": token.access_token, "token_type": token.token_type}
