"""Prompt loader.

Every agent prompt lives as a markdown file under templates/prompts/. Agents
ask for a prompt by key (the filename without extension). Prompts may contain
`{placeholders}` that are filled at runtime with brand voice, context, and the
day's data — so behaviour/tone changes never require touching Python.

A markdown prompt file may optionally contain a `--- system ---` /
`--- user ---` split. If present, the two parts are returned separately; if not,
the whole file is treated as the system prompt and the user content is supplied
by the agent.
"""

from __future__ import annotations

from pathlib import Path

from .errors import PromptNotFoundError
from .logging_config import get_logger

log = get_logger(__name__)

_SYSTEM_MARKER = "--- system ---"
_USER_MARKER = "--- user ---"


class Prompt:
    """A loaded prompt with optional system/user sections and safe formatting."""

    def __init__(self, key: str, system: str, user: str = "") -> None:
        self.key = key
        self.system_template = system
        self.user_template = user

    def render(self, **variables: str) -> tuple[str, str]:
        """Return (system, user) with placeholders substituted.

        Uses str.format_map with a default so an unknown/missing placeholder is
        left intact rather than crashing the run.
        """
        return (
            _safe_format(self.system_template, variables),
            _safe_format(self.user_template, variables),
        )


class _Default(dict):
    def __missing__(self, key: str) -> str:  # leave {unknown} untouched
        return "{" + key + "}"


def _safe_format(template: str, variables: dict[str, str]) -> str:
    return template.format_map(_Default(variables))


class PromptLoader:
    """Loads and caches prompts from a directory of markdown files."""

    def __init__(self, prompts_dir: Path) -> None:
        self.prompts_dir = Path(prompts_dir)
        self._cache: dict[str, Prompt] = {}

    def get(self, key: str) -> Prompt:
        if key in self._cache:
            return self._cache[key]
        path = self.prompts_dir / f"{key}.md"
        if not path.exists():
            raise PromptNotFoundError(
                f"Prompt {key!r} not found at {path}. "
                f"Add a markdown file named {key}.md under templates/prompts/."
            )
        text = path.read_text(encoding="utf-8")
        prompt = self._parse(key, text)
        self._cache[key] = prompt
        log.debug("Loaded prompt %s from %s", key, path)
        return prompt

    @staticmethod
    def _parse(key: str, text: str) -> Prompt:
        lower = text.lower()
        if _SYSTEM_MARKER in lower and _USER_MARKER in lower:
            # Split on the markers case-insensitively but keep original text.
            sys_idx = lower.index(_SYSTEM_MARKER) + len(_SYSTEM_MARKER)
            usr_idx = lower.index(_USER_MARKER)
            system = text[sys_idx:usr_idx].strip()
            user = text[usr_idx + len(_USER_MARKER):].strip()
            return Prompt(key, system, user)
        return Prompt(key, text.strip(), "")
