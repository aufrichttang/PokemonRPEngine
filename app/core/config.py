from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")
    app_name: str = Field(default="pokemon-rp-engine", alias="APP_NAME")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    json_logs: bool = Field(default=True, alias="JSON_LOGS")
    log_to_file: bool = Field(default=True, alias="LOG_TO_FILE")
    log_file_path: str = Field(default="logs/rp-engine.log", alias="LOG_FILE_PATH")
    request_log_enabled: bool = Field(default=True, alias="REQUEST_LOG_ENABLED")
    slow_request_ms: int = Field(default=800, alias="SLOW_REQUEST_MS")
    cors_allowed_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ALLOWED_ORIGINS",
    )

    database_url: str = Field(default="sqlite:///./app.db", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    jwt_secret: str = Field(default="dev-change-me", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=120, alias="JWT_EXPIRE_MINUTES")

    llm_provider: str = Field(default="xfyun_http", alias="LLM_PROVIDER")
    llm_timeout_seconds: int = Field(default=30, alias="LLM_TIMEOUT_SECONDS")
    llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")

    xf_auth_mode: str = Field(default="bearer", alias="XF_AUTH_MODE")
    xf_appid: str = Field(default="", alias="XF_APPID")
    xf_api_key: str = Field(default="", alias="XF_API_KEY")
    xf_api_secret: str = Field(default="", alias="XF_API_SECRET")
    xf_model_id: str = Field(default="xopglm5", alias="XF_MODEL_ID")
    xf_base_url_http: str = Field(
        default="https://maas-api.cn-huabei-1.xf-yun.com/v2", alias="XF_BASE_URL_HTTP"
    )
    xf_base_url_ws: str = Field(
        default="wss://maas-api.cn-huabei-1.xf-yun.com/v1.1/chat", alias="XF_BASE_URL_WS"
    )

    embedding_provider: str = Field(default="fake", alias="EMBEDDING_PROVIDER")
    embedding_dim: int = Field(default=768, alias="EMBEDDING_DIM")

    short_window_turns: int = Field(default=12, alias="SHORT_WINDOW_TURNS")
    vector_top_k: int = Field(default=12, alias="VECTOR_TOP_K")
    timeline_top_n: int = Field(default=8, alias="TIMELINE_TOP_N")
    max_canon_facts: int = Field(default=15, alias="MAX_CANON_FACTS")
    max_recalls: int = Field(default=15, alias="MAX_RECALLS")
    max_open_threads: int = Field(default=10, alias="MAX_OPEN_THREADS")
    max_prompt_tokens_budget: int = Field(default=6000, alias="MAX_PROMPT_TOKENS_BUDGET")

    rate_limit_qps: int = Field(default=5, alias="RATE_LIMIT_QPS")
    rate_limit_burst: int = Field(default=5, alias="RATE_LIMIT_BURST")

    audit_content_enabled: bool = Field(default=True, alias="AUDIT_CONTENT_ENABLED")
    bootstrap_default_admin: bool = Field(default=True, alias="BOOTSTRAP_DEFAULT_ADMIN")
    default_admin_username: str = Field(default="admin", alias="DEFAULT_ADMIN_USERNAME")
    default_admin_password: str = Field(default="admin", alias="DEFAULT_ADMIN_PASSWORD")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
