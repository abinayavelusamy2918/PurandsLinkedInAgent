"""Custom exception hierarchy.

A single base (`PurandsError`) makes it easy to catch any platform error while
still allowing granular handling where needed. Agents should raise these rather
than bare `Exception` so the orchestrator can decide what is fatal vs skippable.
"""

from __future__ import annotations


class PurandsError(Exception):
    """Base class for all platform errors."""


class ConfigError(PurandsError):
    """Raised when configuration is missing, malformed, or invalid."""


class PromptNotFoundError(PurandsError):
    """Raised when a requested prompt key/file does not exist."""


class LLMError(PurandsError):
    """Raised when the LLM provider fails or returns an unusable response."""


class SourceError(PurandsError):
    """Raised when a data source fails to fetch. Usually non-fatal: the
    collector logs it and continues with the remaining sources."""


class AgentError(PurandsError):
    """Raised when an agent cannot complete its task."""
