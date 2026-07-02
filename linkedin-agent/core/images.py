"""Optional image-generation client.

Mirrors `core.llm`: one small interface, swappable providers, a Mock for
dry-run. The Visual Designer agent uses this to turn an image prompt into a real
PNG the user can attach to a LinkedIn post. Image generation is strictly
optional — if it is disabled in config, keys are missing, or a request fails,
the pipeline degrades gracefully to prompt-only (the dashboard still shows the
ready-to-use image prompt so the user can generate it themselves).

Enable it with an `images:` block in config.yaml, e.g.

    images:
      enabled: true
      provider: openai       # openai | mock
      model: gpt-image-1
      size: 1024x1024
"""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .config import require_env
from .logging_config import get_logger

log = get_logger(__name__)


class ImageClient(ABC):
    """Contract for anything that turns a prompt into an image file."""

    def __init__(self, model: str, size: str) -> None:
        self.model = model
        self.size = size

    @abstractmethod
    def generate(self, prompt: str, out_path: Path) -> bool:
        """Generate an image for `prompt` and write it to `out_path`.

        Returns True on success, False on any failure (never raises — a missing
        image must not break the run)."""


class OpenAIImageProvider(ImageClient):
    """OpenAI Images API (e.g. gpt-image-1, dall-e-3). Reads OPENAI_API_KEY."""

    def __init__(self, model: str, size: str) -> None:
        super().__init__(model, size)
        try:
            from openai import OpenAI  # lazy import so dry-run/tests need no SDK
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("openai package not installed; `pip install openai`") from exc
        self._client = OpenAI(api_key=require_env("OPENAI_API_KEY"))

    def generate(self, prompt: str, out_path: Path) -> bool:
        try:
            resp = self._client.images.generate(
                model=self.model, prompt=prompt, size=self.size, n=1,
            )
        except Exception as exc:  # noqa: BLE001 — one failed image must not kill the batch
            log.warning("Image generation failed: %s", exc)
            return False

        datum: Any = resp.data[0] if getattr(resp, "data", None) else None
        if datum is None:
            log.warning("Image API returned no data")
            return False

        out_path.parent.mkdir(parents=True, exist_ok=True)
        b64 = getattr(datum, "b64_json", None)
        if b64:
            out_path.write_bytes(base64.b64decode(b64))
            return True
        url = getattr(datum, "url", None)
        if url:
            try:
                import urllib.request
                urllib.request.urlretrieve(url, out_path)  # noqa: S310 — trusted API URL
                return True
            except Exception as exc:  # noqa: BLE001
                log.warning("Image download failed: %s", exc)
        return False


class MockImageProvider(ImageClient):
    """Dry-run/offline provider. Never calls the network; skips generation so the
    dashboard falls back to showing the image prompt only."""

    def generate(self, prompt: str, out_path: Path) -> bool:
        log.info("MockImageProvider (dry-run) — skipping real image generation")
        return False


_PROVIDERS: dict[str, type[ImageClient]] = {
    "openai": OpenAIImageProvider,
    "mock": MockImageProvider,
}


def build_image_client(config: dict[str, Any], *, mode: str = "full") -> ImageClient | None:
    """Build an image client from the `images:` config block, or return None when
    image generation is disabled/unconfigured (prompt-only fallback)."""
    images = (config or {}).get("images", {}) or {}
    if not images.get("enabled", False):
        return None
    model = str(images.get("model", "gpt-image-1"))
    size = str(images.get("size", "1024x1024"))
    if mode == "dry-run":
        return MockImageProvider(model, size)
    provider = str(images.get("provider", "openai")).lower()
    provider_cls = _PROVIDERS.get(provider)
    if provider_cls is None:
        log.warning("Unknown image provider %r — image generation disabled", provider)
        return None
    try:
        return provider_cls(model, size)
    except Exception as exc:  # noqa: BLE001 — missing key/SDK just disables images
        log.warning("Image client unavailable (%s) — falling back to prompt-only", exc)
        return None
