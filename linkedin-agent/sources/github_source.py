"""GitHub repositories source.

Working via the public GitHub Search API (no token required for low volume; set
GITHUB_TOKEN to raise rate limits). Surfaces recently-active repos matching your
topics so the Trend Hunter can spot emerging tooling. Configure::

    - name: github
      enabled: true
      params:
        queries: [ "retention marketing", "whatsapp commerce", "customer data platform" ]
        max_per_query: 5
"""

from __future__ import annotations

import os

from core.errors import SourceError
from core.models import RawItem
from .base import BaseSource, register_source

_API = "https://api.github.com/search/repositories"


@register_source("github")
class GitHubSource(BaseSource):
    def fetch(self) -> list[RawItem]:
        queries = self.params.get("queries", [])
        per = int(self.params.get("max_per_query", 5))
        if not queries:
            return []
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise SourceError("requests not installed") from exc

        headers = {"Accept": "application/vnd.github+json", "User-Agent": "PurandsAI/1.0"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        items: list[RawItem] = []
        for q in queries:
            params = {"q": f"{q} pushed:>2025-01-01", "sort": "updated", "per_page": per}
            try:
                resp = requests.get(_API, headers=headers, params=params, timeout=20)
                resp.raise_for_status()
            except requests.RequestException as exc:
                raise SourceError(f"GitHub search failed for {q!r}: {exc}") from exc
            for repo in resp.json().get("items", []):
                items.append(RawItem(
                    title=repo.get("full_name", ""),
                    url=repo.get("html_url", ""),
                    source="github:search",
                    summary=(repo.get("description") or "")[:600],
                    published=repo.get("updated_at", ""),
                    raw={"stars": repo.get("stargazers_count", 0), "query": q},
                ))
        return items
