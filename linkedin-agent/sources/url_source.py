"""User-supplied URL source.

Fully working. Fetches each URL and extracts a title + text snippet so you can
feed specific articles into the pipeline on demand::

    - name: urls
      enabled: true
      params:
        urls:
          - https://some-article.example.com
"""

from __future__ import annotations

from core.errors import SourceError
from core.models import RawItem
from .base import BaseSource, register_source


@register_source("urls")
class URLSource(BaseSource):
    def fetch(self) -> list[RawItem]:
        urls = self.params.get("urls", [])
        if not urls:
            return []
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError as exc:  # pragma: no cover
            raise SourceError("requests/beautifulsoup4 not installed") from exc

        items: list[RawItem] = []
        for url in urls:
            try:
                resp = requests.get(url, timeout=20, headers={"User-Agent": "PurandsAI/1.0"})
                resp.raise_for_status()
            except requests.RequestException as exc:
                raise SourceError(f"Failed to fetch {url}: {exc}") from exc
            soup = BeautifulSoup(resp.text, "html.parser")
            title = (soup.title.string if soup.title else url) or url
            text = " ".join(p.get_text(strip=True) for p in soup.find_all("p")[:5])
            items.append(
                RawItem(
                    title=title.strip(),
                    url=url,
                    source="urls:user",
                    summary=text[:600],
                    raw={},
                )
            )
        return items
