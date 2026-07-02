"""LinkedIn post-search source.

Finds recent LinkedIn posts on given topics (AI, tech, etc.) via the Apify
actor `harvestapi/linkedin-post-search` — no LinkedIn account or cookies
required. Each returned RawItem carries the REAL post URL (linkedin.com/posts/…)
so the Engagement Agent can draft a comment and the dashboard can link straight
to the post for one-click navigation.

Requires APIFY_TOKEN (set in .env / GitHub Secrets). Gated: if no token is
present it logs and returns nothing rather than failing the run.

Configure in config/sources.yaml::

    - name: linkedin
      enabled: true
      params:
        search_queries: ["artificial intelligence", "AI agents", "LLM"]
        max_posts_per_query: 10   # posts fetched per query
        posted_limit: week        # any | 1h | 24h | week | month | ...
        sort_by: relevance        # relevance | date
        max_items: 40             # overall cap returned to the pipeline

The actor is not hardcoded to a topic — the queries drive what gets found.
"""

from __future__ import annotations

import os

from core.errors import SourceError
from core.logging_config import get_logger
from core.models import RawItem
from .base import BaseSource, register_source

log = get_logger(__name__)

_DEFAULT_ACTOR = "harvestapi/linkedin-post-search"


@register_source("linkedin")
class LinkedInSource(BaseSource):
    def fetch(self) -> list[RawItem]:
        queries = [q for q in self.params.get("search_queries", []) if q]
        if not queries:
            log.warning("linkedin source has no search_queries — skipping")
            return []

        token = os.getenv("APIFY_TOKEN")
        if not token:
            log.warning("APIFY_TOKEN not set — linkedin source skipped")
            return []

        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise SourceError("requests not installed") from exc

        actor_id = self.params.get("actor_id", _DEFAULT_ACTOR)
        max_per_query = int(self.params.get("max_posts_per_query", 10))
        max_items = int(self.params.get("max_items", 40))
        posted_limit = self.params.get("posted_limit", "week")
        sort_by = self.params.get("sort_by", "relevance")

        run_input = {
            "searchQueries": queries,
            "maxPosts": max_per_query,
            "postedLimit": posted_limit,
            "sortBy": sort_by,
        }
        content_type = self.params.get("content_type")
        if content_type:
            run_input["contentType"] = content_type

        endpoint = (
            f"https://api.apify.com/v2/acts/{actor_id.replace('/', '~')}"
            f"/run-sync-get-dataset-items?token={token}&limit={max_items}"
        )
        try:
            resp = requests.post(endpoint, json=run_input, timeout=180)
            resp.raise_for_status()
            records = resp.json()
        except requests.RequestException as exc:
            raise SourceError(f"LinkedIn actor {actor_id} failed: {exc}") from exc

        items: list[RawItem] = []
        for rec in records[:max_items]:
            if not isinstance(rec, dict):
                continue
            content = (rec.get("content") or "").strip()
            url = rec.get("linkedinUrl") or rec.get("shareLinkedinUrl") or ""
            # Skip anything without both text to react to and a link to visit.
            if not content or not url:
                continue
            author = rec.get("author") or {}
            author_name = author.get("name", "") if isinstance(author, dict) else ""
            author_url = author.get("linkedinUrl", "") if isinstance(author, dict) else ""
            posted = rec.get("postedAt") or {}
            posted_ago = posted.get("postedAgoText", "") if isinstance(posted, dict) else ""
            engagement = rec.get("engagement") or {}

            first_line = content.splitlines()[0][:120] if content else ""
            title = f"{author_name}: {first_line}".strip(": ") or "LinkedIn post"

            items.append(RawItem(
                title=title[:300],
                url=url,
                source="linkedin",
                summary=content[:800],
                published=(posted.get("date", "") if isinstance(posted, dict) else ""),
                raw={
                    "author": author_name,
                    "author_url": author_url,
                    "posted_ago": posted_ago,
                    "likes": engagement.get("likes") if isinstance(engagement, dict) else None,
                    "comments": engagement.get("comments") if isinstance(engagement, dict) else None,
                },
            ))
        log.info("linkedin source returned %d posts", len(items))
        return items
