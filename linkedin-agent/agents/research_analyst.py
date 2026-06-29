"""Agent 2 — Research Analyst.

Verifies each trend: gathers evidence, statistics, examples, recent news, and
risks; assigns a confidence score; and rejects weak/unsupported claims. Only
accepted trends flow downstream. Attaches results to ctx.researched.
"""

from __future__ import annotations

import json

from core.models import (
    AgentResult, Evidence, ResearchedTrend, RunContext, Trend,
)
from .base import BaseAgent, register


@register("research_analyst")
class ResearchAnalyst(BaseAgent):
    def execute(self, ctx: RunContext) -> AgentResult:
        if not ctx.trends:
            self.log.warning("No trends to research")
            return AgentResult(agent=self.name, ok=True, data=[])

        if self.dry_run(ctx):
            ctx.researched = [self._sample(t) for t in ctx.trends]
            return AgentResult(agent=self.name, ok=True,
                               data=[r.to_dict() for r in ctx.researched])

        prompt = self.prompts.get("research_analyst")
        system, user = prompt.render(
            purands_context=self.brand(ctx, "purands_context"),
            run_date=ctx.run_date,
            trends=json.dumps([t.to_dict() for t in ctx.trends], ensure_ascii=False, indent=2),
        )
        data = self.llm.complete_json(system, user)
        researched = [_to_researched(d, ctx.trends) for d in (data or [])]
        # Keep only accepted ones for downstream content; retain all for the report.
        ctx.researched = researched
        accepted = [r for r in researched if r.verdict == "accepted"]
        self.log.info("Researched %d trends; %d accepted", len(researched), len(accepted))
        return AgentResult(agent=self.name, ok=True, data=[r.to_dict() for r in researched])

    def _sample(self, trend: Trend) -> ResearchedTrend:
        return ResearchedTrend(
            trend=trend,
            confidence=0.72,
            evidence=[Evidence(claim="Sample claim", support="Sample supporting stat",
                               url="https://example.com")],
            statistics=["Sample: 30% higher reply rate (dry-run)"],
            examples=["Sample brand example"],
            recent_news=["Sample recent news item"],
            risks=["Sample risk / caveat"],
            verdict="accepted",
        )


def _to_researched(d: dict, trends: list[Trend]) -> ResearchedTrend:
    raw_trend = d.get("trend", {})
    trend = _match_trend(raw_trend, trends)
    evidence = [
        Evidence(claim=e.get("claim", ""), support=e.get("support", ""), url=e.get("url", ""))
        for e in d.get("evidence", [])
    ]
    return ResearchedTrend(
        trend=trend,
        confidence=float(d.get("confidence", 0.0) or 0.0),
        evidence=evidence,
        statistics=list(d.get("statistics", [])),
        examples=list(d.get("examples", [])),
        recent_news=list(d.get("recent_news", [])),
        risks=list(d.get("risks", [])),
        verdict=d.get("verdict", "accepted"),
        reject_reason=d.get("reject_reason", ""),
    )


def _match_trend(raw: dict, trends: list[Trend]) -> Trend:
    """Match the echoed trend back to the original by title; fall back to a
    reconstructed Trend if the model altered it."""
    title = (raw.get("title") or "").strip().lower()
    for t in trends:
        if t.title.strip().lower() == title:
            return t
    return Trend(
        title=raw.get("title", ""),
        category=raw.get("category", ""),
        rank=int(raw.get("rank", 0) or 0),
        rationale=raw.get("rationale", ""),
        signals=list(raw.get("signals", [])),
        sources=list(raw.get("sources", [])),
        region=raw.get("region", "APAC"),
    )
