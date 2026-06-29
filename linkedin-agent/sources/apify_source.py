"""Apify actor source.

Runs an Apify actor and maps its dataset items to RawItems. Requires APIFY_TOKEN
(set as a GitHub Secret / .env). Gated: if no token is present it logs and
returns nothing rather than failing the run. Configure::

    - name: apify
      enabled: true
      params:
        actor_id: "apify/website-content-crawler"
        run_input: { startUrls: [ { url: "https://example.com" } ] }
        max_items: 20
        title_field: title
        url_field: url
        text_field: text

The field-mapping params keep this generic across different actors — no actor is
hardcoded.
"""

from __future__ import annotations

import os

from core.errors import SourceError
from core.logging_config import get_logger
from core.models import RawItem
from .base import BaseSource, register_source

log = get_logger(__name__)


@register_source("apify")
class ApifySource(BaseSource):
    def fetch(self) -> list[RawItem]:
        token = os.getenv("APIFY_TOKEN")
        if not token:
            log.warning("APIFY_TOKEN not set — apify source skipped")
            return []
        actor_id = self.params.get("actor_id")
        if not actor_id:
            raise SourceError("apify source requires 'actor_id' in params")

        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise SourceError("requests not installed") from exc

        run_input = self.params.get("run_input", {})
        max_items = int(self.params.get("max_items", 20))
        t_field = self.params.get("title_field", "title")
        u_field = self.params.get("url_field", "url")
        x_field = self.params.get("text_field", "text")

        # Run actor synchronously and read its dataset items.
        endpoint = (
            f"https://api.apify.com/v2/acts/{actor_id.replace('/', '~')}"
            f"/run-sync-get-dataset-items?token={token}&limit={max_items}"
        )
        try:
            resp = requests.post(endpoint, json=run_input, timeout=120)
            resp.raise_for_status()
            records = resp.json()
        except requests.RequestException as exc:
            raise SourceError(f"Apify actor {actor_id} failed: {exc}") from exc

        items: list[RawItem] = []
        for rec in records[:max_items]:
            items.append(RawItem(
                title=str(rec.get(t_field, ""))[:300],
                url=str(rec.get(u_field, "")),
                source=f"apify:{actor_id}",
                summary=str(rec.get(x_field, ""))[:600],
                raw=rec if isinstance(rec, dict) else {},
            ))
        return items
