"""Pipeline orchestrator.

Builds the agent pipeline from config, wires shared dependencies (LLM, prompts),
loads brand knowledge + data sources into the RunContext, runs each agent in
order, and persists per-run JSON artifacts. The orchestrator knows nothing about
any specific agent — only the names listed in config.yaml's `pipeline`.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from agents.base import get_agent_class
from core.config import Settings
from core.llm import build_llm
from core.logging_config import get_logger
from core.models import RunContext
from core.prompts import PromptLoader

log = get_logger(__name__)


def load_brand(data_dir: Path) -> dict[str, str]:
    """Read every brand .md file in data/ into a dict keyed by filename stem.

    Read dynamically so editing brand_voice.md etc. needs no code change.
    """
    brand: dict[str, str] = {}
    for md in sorted(data_dir.glob("*.md")):
        brand[md.stem] = md.read_text(encoding="utf-8")
    if not brand:
        log.warning("No brand .md files found in %s", data_dir)
    return brand


class Orchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = build_llm(settings.llm, mode=settings.mode)
        self.prompts = PromptLoader(settings.path("prompts"))

    def build_context(self, run_date: str | None = None) -> RunContext:
        run_date = run_date or date.today().isoformat()
        brand = load_brand(self.settings.path("data"))
        # Compose a single config dict for agents: config.yaml values plus the
        # parsed sources list and the resolved mode. Agents read everything they
        # need from ctx.config, keeping them decoupled from Settings internals.
        config = dict(self.settings.raw)
        config["mode"] = self.settings.mode
        config["_sources_list"] = self.settings.sources.get("sources", [])
        return RunContext(
            run_date=run_date,
            config=config,
            brand=brand,
        )

    def run(self, ctx: RunContext) -> RunContext:
        for agent_name in self.settings.pipeline:
            agent_cls = get_agent_class(agent_name)
            agent = agent_cls(self.llm, self.prompts)
            result = agent.run(ctx)
            ctx.results.append(result)
            if not result.ok:
                log.error("Agent %s failed: %s — continuing pipeline", agent_name, result.error)
        self._persist(ctx)
        return ctx

    def _persist(self, ctx: RunContext) -> None:
        """Write run artifacts to data/runs/<date>/ for auditing and re-runs."""
        run_dir = self.settings.path("runs") / ctx.run_date
        run_dir.mkdir(parents=True, exist_ok=True)
        artifacts: dict[str, Any] = {
            "trends": [t.to_dict() for t in ctx.trends],
            "researched": [r.to_dict() for r in ctx.researched],
            "drafts": [d.to_dict() for d in ctx.drafts],
            "comments": [c.to_dict() for c in ctx.comments],
            "replies": [r.to_dict() for r in ctx.replies],
            "results": [r.to_dict() for r in ctx.results],
        }
        for name, payload in artifacts.items():
            (run_dir / f"{name}.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        log.info("Persisted run artifacts to %s", run_dir)
