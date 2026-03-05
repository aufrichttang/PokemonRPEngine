import contextvars
import logging
import sys
from pathlib import Path
from typing import Any

import structlog

from app.core.config import get_settings

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")


class RedactSecretsProcessor:
    """Redact known sensitive keys from structured logs."""

    SENSITIVE_KEYS = {"authorization", "xf_api_secret", "xf_api_key", "password", "jwt_secret"}

    def _scrub(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                if key.lower() in self.SENSITIVE_KEYS:
                    sanitized[key] = "***"
                else:
                    sanitized[key] = self._scrub(item)
            return sanitized
        if isinstance(value, list):
            return [self._scrub(item) for item in value]
        return value

    def __call__(
        self, _logger: Any, _method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        return self._scrub(event_dict)


def add_trace_id(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    event_dict["trace_id"] = trace_id_var.get()
    return event_dict


def configure_logging() -> None:
    settings = get_settings()

    handlers: list[logging.Handler] = [logging.StreamHandler(stream=sys.stdout)]
    if settings.log_to_file and settings.log_file_path:
        log_path = Path(settings.log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    logging.basicConfig(
        format="%(message)s",
        level=settings.log_level,
        handlers=handlers,
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        add_trace_id,
        RedactSecretsProcessor(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
