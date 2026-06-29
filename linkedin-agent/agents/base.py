"""Agent base class and registry.

Every agent subclasses `BaseAgent` and implements `execute(ctx)`. The public
`run(ctx)` wrapper handles timing, logging, and error capture uniformly so an
individual agent failure never crashes the whole pipeline — it returns a failed
`AgentResult` and the orchestrator decides whether to continue.

The `@register("name")` decorator adds the class to a global registry keyed by
the name used in config.yaml's `pipeline`. This is what makes new agents
drop-in: no orchestrator edits required.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Callable

from core.errors import AgentError
from core.llm import LLMClient
from core.logging_config import get_logger
from core.models import AgentResult, RunContext
from core.prompts import PromptLoader

log = get_logger(__name__)

_REGISTRY: dict[str, type["BaseAgent"]] = {}


def register(name: str) -> Callable[[type["BaseAgent"]], type["BaseAgent"]]:
    """Class decorator that registers an agent under `name`."""
    def _wrap(cls: type["BaseAgent"]) -> type["BaseAgent"]:
        if name in _REGISTRY:
            raise AgentError(f"Agent name already registered: {name!r}")
        cls.name = name
        _REGISTRY[name] = cls
        return cls
    return _wrap


def get_agent_class(name: str) -> type["BaseAgent"]:
    if name not in _REGISTRY:
        raise AgentError(
            f"No agent registered as {name!r}. "
            f"Registered agents: {', '.join(sorted(_REGISTRY)) or '(none)'}"
        )
    return _REGISTRY[name]


def registered_agents() -> list[str]:
    return sorted(_REGISTRY)


class BaseAgent(ABC):
    """Common contract + lifecycle for all agents."""

    name: str = "base"

    def __init__(self, llm: LLMClient, prompts: PromptLoader) -> None:
        self.llm = llm
        self.prompts = prompts
        self.log = get_logger(f"agent.{self.name}")

    @abstractmethod
    def execute(self, ctx: RunContext) -> AgentResult:
        """Do the agent's work. Must return an AgentResult. Raise on failure;
        `run()` will catch and wrap it."""

    def dry_run(self, ctx: RunContext) -> bool:
        """True when running offline with the mock provider (mode: dry-run).
        Agents return small sample payloads in this mode so the full pipeline
        and HTML rendering can be exercised without an API key."""
        return ctx.config.get("mode") == "dry-run"

    def brand(self, ctx: RunContext, name: str) -> str:
        """Fetch a brand .md file's contents by stem (e.g. 'brand_voice')."""
        return ctx.brand.get(name, "")

    def run(self, ctx: RunContext) -> AgentResult:
        """Public entry point with uniform timing/logging/error handling."""
        started = datetime.now(timezone.utc).isoformat()
        self.log.info("Starting %s", self.name)
        try:
            result = self.execute(ctx)
            result.finished_at = datetime.now(timezone.utc).isoformat()
            self.log.info("Completed %s (ok=%s)", self.name, result.ok)
            return result
        except Exception as exc:  # noqa: BLE001 — capture so pipeline survives
            self.log.exception("Agent %s failed", self.name)
            return AgentResult(
                agent=self.name,
                ok=False,
                error=str(exc),
                started_at=started,
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
