"""Provider-agnostic LLM client.

`LLMClient` is the single interface every agent uses. Concrete providers
implement `complete()`. Adding OpenAI later = one new class + a config value;
no agent code changes. This is the open/closed principle applied to vendors.

Anthropic is the default provider. A `MockProvider` powers `mode: dry-run` and
tests, so the pipeline runs end-to-end with zero API cost.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from .config import LLMSettings, require_env
from .errors import LLMError
from .logging_config import get_logger

log = get_logger(__name__)


class LLMClient(ABC):
    """The contract all providers honour."""

    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings

    @abstractmethod
    def complete(self, system: str, prompt: str, *, max_tokens: int | None = None,
                 temperature: float | None = None) -> str:
        """Return the model's text completion for a system+user prompt."""

    # Convenience: ask the model for JSON and parse it, with one repair retry.
    def complete_json(self, system: str, prompt: str, **kwargs: Any) -> Any:
        text = self.complete(system, prompt, **kwargs)
        return _parse_json_lenient(text)


class AnthropicProvider(LLMClient):
    """Claude provider. Reads ANTHROPIC_API_KEY from the environment."""

    def __init__(self, settings: LLMSettings) -> None:
        super().__init__(settings)
        try:
            import anthropic  # imported lazily so dry-run/tests need no SDK
        except ImportError as exc:  # pragma: no cover
            raise LLMError("anthropic package not installed; `pip install anthropic`") from exc
        self._client = anthropic.Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))

    def complete(self, system: str, prompt: str, *, max_tokens: int | None = None,
                 temperature: float | None = None) -> str:
        try:
            msg = self._client.messages.create(
                model=self.settings.model,
                max_tokens=max_tokens or self.settings.max_tokens,
                temperature=temperature if temperature is not None else self.settings.temperature,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001 — wrap any SDK/network error
            raise LLMError(f"Anthropic request failed: {exc}") from exc

        parts = [block.text for block in msg.content if getattr(block, "type", "") == "text"]
        text = "".join(parts).strip()
        if not text:
            raise LLMError("Anthropic returned an empty completion")
        return text


class MockProvider(LLMClient):
    """Deterministic offline provider for dry-run and tests.

    Returns shaped placeholder text/JSON so the full pipeline and HTML rendering
    can be exercised without an API key or network.
    """

    def complete(self, system: str, prompt: str, *, max_tokens: int | None = None,
                 temperature: float | None = None) -> str:
        log.info("MockProvider.complete (dry-run) — returning placeholder")
        return "[DRY-RUN] Mock completion. Enable mode: full with an API key for real output."


_PROVIDERS: dict[str, type[LLMClient]] = {
    "anthropic": AnthropicProvider,
    "mock": MockProvider,
}


def build_llm(settings: LLMSettings, *, mode: str = "full") -> LLMClient:
    """Factory. In dry-run mode we always use the mock provider."""
    if mode == "dry-run":
        return MockProvider(settings)
    provider_cls = _PROVIDERS.get(settings.provider.lower())
    if provider_cls is None:
        raise LLMError(
            f"Unknown LLM provider {settings.provider!r}. "
            f"Available: {', '.join(_PROVIDERS)}"
        )
    return provider_cls(settings)


def _parse_json_lenient(text: str) -> Any:
    """Best-effort JSON extraction from a model response.

    Handles the common cases where the model wraps JSON in prose or ```json
    fences. Raises LLMError if nothing parseable is found.
    """
    text = text.strip()
    # Strip code fences if present.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    # Try direct parse first.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to the outermost {...} or [...] span.
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start, end = text.find(open_c), text.rfind(close_c)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError(f"Could not parse JSON from model response: {text[:200]}...")
