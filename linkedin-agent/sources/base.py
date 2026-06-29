"""Source base class, registry, and the collector.

Each source implements `fetch() -> list[RawItem]`. The collector reads
config/sources.yaml, instantiates only the enabled sources with their params,
and aggregates their items. A failing source is logged and skipped — one broken
feed never aborts the run.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from core.errors import SourceError
from core.logging_config import get_logger
from core.models import RawItem

log = get_logger(__name__)

_SOURCE_REGISTRY: dict[str, type["BaseSource"]] = {}


def register_source(name: str) -> Callable[[type["BaseSource"]], type["BaseSource"]]:
    def _wrap(cls: type["BaseSource"]) -> type["BaseSource"]:
        cls.source_name = name
        _SOURCE_REGISTRY[name] = cls
        return cls
    return _wrap


class BaseSource(ABC):
    """Contract for a data source."""

    source_name: str = "base"

    def __init__(self, params: dict[str, Any]) -> None:
        self.params = params or {}

    @abstractmethod
    def fetch(self) -> list[RawItem]:
        """Return raw items. Raise SourceError on failure."""


def collect(sources_cfg: dict[str, Any], *, mode: str = "full") -> list[RawItem]:
    """Instantiate and run all enabled sources from config.

    sources_cfg is the parsed sources.yaml. Expected shape::

        sources:
          - name: rss
            enabled: true
            params: { feeds: [...] }

    In dry-run mode, sources may return small static samples (each source
    decides). The collector itself is provider-agnostic.
    """
    items: list[RawItem] = []
    entries = sources_cfg.get("sources", [])
    if not entries:
        log.warning("No sources configured in sources.yaml")
    for entry in entries:
        name = entry.get("name")
        if not entry.get("enabled", False):
            log.info("Source %s disabled — skipping", name)
            continue
        cls = _SOURCE_REGISTRY.get(name)
        if cls is None:
            log.error("Unknown source %r (registered: %s) — skipping",
                      name, ", ".join(sorted(_SOURCE_REGISTRY)))
            continue
        params = dict(entry.get("params", {}))
        params["_mode"] = mode  # let sources know if we're in dry-run
        try:
            fetched = cls(params).fetch()
            log.info("Source %s returned %d items", name, len(fetched))
            items.extend(fetched)
        except SourceError as exc:
            log.error("Source %s failed: %s — skipping", name, exc)
        except Exception as exc:  # noqa: BLE001
            log.exception("Unexpected error in source %s — skipping", name)
    return items


def registered_sources() -> list[str]:
    return sorted(_SOURCE_REGISTRY)
