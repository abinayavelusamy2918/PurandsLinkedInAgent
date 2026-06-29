"""Agent 5 — Editor & Publisher.

Produces an editorial assessment (publishing recommendation + risk assessment)
and renders the daily review dashboard HTML into output/daily/. Does NOT publish
anything — the dashboard is for human review.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.config import PACKAGE_ROOT
from core.models import AgentResult, RunContext
from rendering.renderer import render_dashboard
from .base import BaseAgent, register


@register("editor_publisher")
class EditorPublisher(BaseAgent):
    def execute(self, ctx: RunContext) -> AgentResult:
        editorial = self._assess(ctx)

        out_dir = Path(ctx.config.get("paths", {}).get("output_daily", "output/daily"))
        out_path = render_dashboard(ctx, editorial, PACKAGE_ROOT / out_dir)
        self.log.info("Wrote daily dashboard: %s", out_path)

        return AgentResult(
            agent=self.name, ok=True,
            data={"editorial": editorial, "html": str(out_path)},
        )

    def _assess(self, ctx: RunContext) -> dict:
        # Default editorial when there's nothing to assess or in dry-run.
        default = {
            "publishing_recommendation": "hold",
            "reasoning": "No high-confidence post available." if not ctx.drafts else "Review before publishing.",
            "risk_assessment": [],
            "summary": "Automated daily run output for review.",
        }
        if self.dry_run(ctx) or not ctx.drafts:
            if self.dry_run(ctx):
                default["summary"] = "[DRY-RUN] Sample editorial assessment."
                default["publishing_recommendation"] = "revise"
            return default

        prompt = self.prompts.get("editor_publisher")
        top = sorted(ctx.researched, key=lambda r: r.confidence, reverse=True)[:3]
        system, user = prompt.render(
            brand_voice=self.brand(ctx, "brand_voice"),
            run_date=ctx.run_date,
            researched=json.dumps([r.to_dict() for r in top], ensure_ascii=False, indent=2),
            draft=json.dumps(ctx.drafts[0].to_dict(), ensure_ascii=False, indent=2),
            comments=json.dumps([c.to_dict() for c in ctx.comments], ensure_ascii=False, indent=2),
        )
        try:
            d = self.llm.complete_json(system, user)
        except Exception as exc:  # noqa: BLE001 — never let editor crash the run
            self.log.warning("Editorial LLM assessment failed: %s — using default", exc)
            return default
        return {
            "publishing_recommendation": d.get("publishing_recommendation", "hold"),
            "reasoning": d.get("reasoning", ""),
            "risk_assessment": list(d.get("risk_assessment", [])),
            "summary": d.get("summary", ""),
        }
