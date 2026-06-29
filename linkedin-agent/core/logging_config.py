"""Centralised logging setup.

Call `configure_logging()` once at startup (the entry point does this). Every
module then uses `logging.getLogger(__name__)` and inherits a consistent format.
Keeping this in one place means we can later swap to JSON logs or add a file
handler without touching any agent.
"""

from __future__ import annotations

import logging
import os
import sys

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(level: str | None = None) -> None:
    """Configure the root logger.

    Args:
        level: Log level name (e.g. "INFO", "DEBUG"). Falls back to the
            LOG_LEVEL env var, then "INFO".
    """
    resolved = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, resolved, logging.INFO),
        format=_DEFAULT_FORMAT,
        stream=sys.stdout,
        force=True,  # re-configure cleanly if called again (e.g. in tests)
    )
    # Quiet noisy third-party loggers.
    for noisy in ("httpx", "urllib3", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper so modules don't import logging directly."""
    return logging.getLogger(name)
