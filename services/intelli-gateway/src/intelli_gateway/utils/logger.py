"""Structured JSON logs with the request_id of the request being served.

Log with `logger.info("event_name", extra={"fields": {...}})`; the fields become top-level JSON
keys. Never put secrets or API keys in fields.
"""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            entry.update(fields)  # pyright: ignore[reportUnknownArgumentType]
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    package_logger = logging.getLogger("intelli_gateway")
    package_logger.handlers = [handler]
    package_logger.setLevel(level.upper())
    package_logger.propagate = False
