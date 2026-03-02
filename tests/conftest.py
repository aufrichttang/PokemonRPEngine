from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB_PATH = Path("test.db")
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/9"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "fake"
os.environ["XF_API_KEY"] = "test"
os.environ["XF_API_SECRET"] = "test"
os.environ["XF_APPID"] = "test"
os.environ["RATE_LIMIT_QPS"] = "1000"

from app.api.deps import (
    get_embed_provider,
    get_llm_provider,
    get_rate_limiter,
    get_security_service,
)
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app

get_settings.cache_clear()
get_llm_provider.cache_clear()
get_embed_provider.cache_clear()
get_rate_limiter.cache_clear()
get_security_service.cache_clear()

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session():
    with SessionLocal() as db:
        yield db
