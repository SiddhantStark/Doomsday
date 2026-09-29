"""JSON logs with redaction applied after exception formatting."""

import json
import logging
import re

from .time_utils import now_ist


class RedactingFormatter(logging.Formatter):
    def __init__(self, secrets: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.secrets = tuple(value for value in secrets if value)

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            message += " " + self.formatException(record.exc_info)
        for value in sorted(self.secrets, key=len, reverse=True):
            message = message.replace(value, "[REDACTED]")
        message = re.sub(r"\b\d+:[A-Za-z0-9_-]{15,}\b", "[REDACTED]", message)
        return json.dumps(
            {
                "timestamp": now_ist().isoformat(),
                "level": record.levelname,
                "message": message,
            }
        )


def configure_logging(level: str, secrets: tuple[str, ...]) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter(secrets))
    logging.basicConfig(level=level, handlers=[handler], force=True)
