"""Agent 1 — Trend Hunter.

Collects raw items from the enabled data sources, then asks the LLM to identify
and rank the most important current discussions. Produces Trend objects only —
no generated content. Attaches them to ctx.trends.
"""

from __future__ import annotations

import json

from core.models import AgentResult, RunContext, Trend
from sources.base import collect
from .base import BaseAgent, register


@register("trend_hunter")
class TrendHunter(BaseAgent):
    def execute(self, ctx: RunContext) -> AgentResult:
        max_trends = int(ctx.config.get("limits", {}).get("max_trends", 8))

        # Dry-run stays fully offline: no source collection, no LLM call.
        if self.dry_run(ctx):
            ctx.trends = self._sample()
            return AgentResult(agent=self.name, ok=True, data=[t.to_dict() for t in ctx.trends])

        # 1) Collect raw items (Trend Hunter is the consumer of the source layer).
        # The orchestrator injects the parsed sources.yaml list under
        # ctx.config["_sources_list"].
        ctx.raw_items = collect(
            {"sources": ctx.config.get("_sources_list", [])},
            mode=ctx.config.get("mode", "full"),
        )
        self.log.info("Collected %d raw items", len(ctx.raw_items))

        # 2) Rank via LLM.
        prompt = self.prompts.get("trend_hunter")
        system, user = prompt.render(
            purands_context=self.brand(ctx, "purands_context"),
            approved_topics=self.brand(ctx, "approved_topics"),
            blocked_topics=self.brand(ctx, "blocked_topics"),
            run_date=ctx.run_date,
            max_trends=str(max_trends),
            raw_items=_format_items(ctx.raw_items),
        )
        data = self.llm.complete_json(system, user)
        trends = [_to_trend(d) for d in (data or [])][:max_trends]
        ctx.trends = trends
        return AgentResult(agent=self.name, ok=True, data=[t.to_dict() for t in trends])

    def _sample(self) -> list[Trend]:
        return [
            Trend(
                title="WhatsApp-first win-back flows outperform email in APAC",
                category="WhatsApp Commerce",
                rank=1,
                rationale="Sample (dry-run) trend for offline pipeline testing.",
                signals=["high open rates", "mobile-first markets"],
                sources=["https://example.com/whatsapp-winback"],
            )
        ]


def _format_items(items) -> str:
    lines = []
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. [{it.source}] {it.title} — {it.url}\n   {it.summary[:200]}")
    return "\n".join(lines) if lines else "(no items collected)"


def _to_trend(d: dict) -> Trend:
    return Trend(
        title=d.get("title", ""),
        category=d.get("category", ""),
        rank=int(d.get("rank", 0) or 0),
        rationale=d.get("rationale", ""),
        signals=list(d.get("signals", [])),
        sources=list(d.get("sources", [])),
        region=d.get("region", "APAC"),
    )
