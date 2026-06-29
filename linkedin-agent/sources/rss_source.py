"""RSS / Atom feed source.

Fully working. Configure feeds in sources.yaml::

    - name: rss
      enabled: true
      params:
        feeds:
          - https://example.com/feed.xml
        max_items_per_feed: 10
"""

from __future__ import annotations

from core.errors import SourceError
from core.models import RawItem
from .base import BaseSource, register_source


@register_source("rss")
class RSSSource(BaseSource):
    def fetch(self) -> list[RawItem]:
        feeds = self.params.get("feeds", [])
        limit = int(self.params.get("max_items_per_feed", 10))
        if not feeds:
            return []
        try:
            import feedparser
        except ImportError as exc:  # pragma: no cover
            raise SourceError("feedparser not installed; `pip install feedparser`") from exc

        items: list[RawItem] = []
        for feed_url in feeds:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:limit]:
                items.append(
                    RawItem(
                        title=getattr(entry, "title", "").strip(),
                        url=getattr(entry, "link", "").strip(),
                        source=f"rss:{_short(feed_url)}",
                        summary=getattr(entry, "summary", "")[:600],
                        published=getattr(entry, "published", ""),
                        raw={"feed": feed_url},
                    )
                )
        return items


def _short(url: str) -> str:
    return url.split("//")[-1].split("/")[0]
