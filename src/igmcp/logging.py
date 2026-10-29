"""structlog JSON logging with token redaction."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

_TOKEN_RE = re.compile(r"(access_token=|Bearer\s+)[A-Za-z0-9_\-\.]+", re.IGNORECASE)
_BARE_TOKEN_RE = re.compile(r"\bEAA[A-Za-z0-9]{20,}\b")


def redact(text: str) -> str:
    return _BARE_TOKEN_RE.sub("[redacted]", _TOKEN_RE.sub(r"\1[redacted]", text))


def _redact_processor(_: Any, __: str, event: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    for key, value in list(event.items()):
        if isinstance(value, str):
            event[key] = redact(value)
    return event


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(stream=sys.stdout, level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
    )
