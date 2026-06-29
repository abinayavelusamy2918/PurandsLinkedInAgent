"""AI company / tech blog source.

Working. Many company blogs expose an RSS feed; if a feed URL is given we use
it, otherwise we scrape article links from an index page. Configure::

    - name: blogs
      enabled: true
      params:
        feeds: [ https://www.anthropic.com/rss.xml ]
        pages: [ https://some-blog.example.com/blog ]
        max_items: 8
"""

from __future__ import annotations

from urllib.parse import urljoin

from core.errors import SourceError
from core.models import RawItem
from .base import BaseSource, register_source


@register_source("blogs")
class BlogSource(BaseSource):
    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        max_items = int(self.params.get("max_items", 8))

        for feed in self.params.get("feeds", []):
            items.extend(self._from_feed(feed, max_items))
        for page in self.params.get("pages", []):
            items.extend(self._from_page(page, max_items))
        return items

    def _from_feed(self, feed_url: str, limit: int) -> list[RawItem]:
        try:
            import feedparser
        except ImportError as exc:  # pragma: no cover
            raise SourceError("feedparser not installed") from exc
        parsed = feedparser.parse(feed_url)
        out = []
        for entry in parsed.entries[:limit]:
            out.append(RawItem(
                title=getattr(entry, "title", "").strip(),
                url=getattr(entry, "link", "").strip(),
                source=f"blog:{_host(feed_url)}",
                summary=getattr(entry, "summary", "")[:600],
                published=getattr(entry, "published", ""),
            ))
        return out

    def _from_page(self, page_url: str, limit: int) -> list[RawItem]:
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError as exc:  # pragma: no cover
            raise SourceError("requests/beautifulsoup4 not installed") from exc
        try:
            resp = requests.get(page_url, timeout=20, headers={"User-Agent": "PurandsAI/1.0"})
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise SourceError(f"Failed to fetch {page_url}: {exc}") from exc
        soup = BeautifulSoup(resp.text, "html.parser")
        out, seen = [], set()
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = urljoin(page_url, a["href"])
            if len(text) < 25 or href in seen:
                continue
            seen.add(href)
            out.append(RawItem(title=text, url=href, source=f"blog:{_host(page_url)}"))
            if len(out) >= limit:
                break
        return out


def _host(url: str) -> str:
    return url.split("//")[-1].split("/")[0]
