"""
Structured logging configuration.

Uses stdlib `logging` with a formatter that always includes component/module
context, so log lines answer "what happened, when, and where" without extra
ceremony at each call site. Never route secrets into log records — callers
are responsible for not passing them, and this module doesn't do string
interpolation of arbitrary user input into the message template without it
going through `%s` args (avoids accidental log injection via format strings).
"""

from __future__ import annotations

import logging
import sys


_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())

    # Avoid duplicate handlers if configure_logging is called more than once
    # (e.g. in tests that import the app repeatedly).
    if root.handlers:
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(handler)

    # Third-party libraries are noisy at INFO/DEBUG; keep them at WARNING
    # unless we're actively debugging.
    for noisy_logger in ("httpx", "httpcore", "telegram"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
