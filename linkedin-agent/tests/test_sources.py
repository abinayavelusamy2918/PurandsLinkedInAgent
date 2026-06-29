"""Source registry + collector resilience."""

import sources  # noqa: F401  (registers sources)
from core.models import RawItem
from sources.base import (
    BaseSource, collect, register_source, registered_sources,
)


def test_builtin_sources_registered():
    reg = set(registered_sources())
    for name in ["rss", "news", "blogs", "github", "urls", "apify"]:
        assert name in reg


def test_disabled_sources_are_skipped():
    cfg = {"sources": [{"name": "rss", "enabled": False, "params": {}}]}
    assert collect(cfg) == []


def test_failing_source_does_not_abort_collection():
    @register_source("boom_test")
    class BoomSource(BaseSource):
        def fetch(self):
            raise RuntimeError("kaboom")

    @register_source("ok_test")
    class OkSource(BaseSource):
        def fetch(self):
            return [RawItem(title="ok", url="http://x", source="ok_test")]

    cfg = {"sources": [
        {"name": "boom_test", "enabled": True, "params": {}},
        {"name": "ok_test", "enabled": True, "params": {}},
    ]}
    items = collect(cfg)
    # The failing source is skipped; the good one still returns its item.
    assert len(items) == 1 and items[0].title == "ok"
