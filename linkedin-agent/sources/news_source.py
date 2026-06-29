"""Technology / business news source.

Working via RSS (most outlets publish feeds). This is intentionally a thin
specialisation of feed handling so news can be tuned (e.g. keyword filtering)
independently of generic RSS. Configure::

    - name: news
      enabled: true
      params:
        feeds: [ https://feeds.example.com/tech ]
        keywords: [ retention, loyalty, whatsapp, shopify, crm ]
        max_items: 12
"""

from __future__ import annotations

from core.errors import SourceError
from core.models import RawItem
from .base import BaseSource, register_source


@register_source("news")
class NewsSource(BaseSource):
    def fetch(self) -> list[RawItem]:
        feeds = self.params.get("feeds", [])
        keywords = [k.lower() for k in self.params.get("keywords", [])]
        limit = int(self.params.get("max_items", 12))
        if not feeds:
            return []
        try:
            import feedparser
        except ImportError as exc:  # pragma: no cover
            raise SourceError("feedparser not installed") from exc

        items: list[RawItem] = []
        for feed_url in feeds:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries:
                title = getattr(entry, "title", "").strip()
                summary = getattr(entry, "summary", "")
                if keywords and not _matches(f"{title} {summary}".lower(), keywords):
                    continue
                items.append(RawItem(
                    title=title,
                    url=getattr(entry, "link", "").strip(),
                    source=f"news:{feed_url.split('//')[-1].split('/')[0]}",
                    summary=summary[:600],
                    published=getattr(entry, "published", ""),
                ))
                if len(items) >= limit:
                    break
        return items


def _matches(text: str, keywords: list[str]) -> bool:
    return any(k in text for k in keywords)
