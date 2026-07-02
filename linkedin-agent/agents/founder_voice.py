"""Agent 3 — Founder Voice.

Writes LinkedIn posts in a Purands AI co-founder's voice — ONE post per
accepted, high-confidence trend, up to limits.max_posts (default 10). Each post
has a body, three alternative hooks, a CTA, and relevant hashtags, and records
which trend it was based on so the dashboard can show the research behind it.
Attaches the list of DraftPosts to ctx.drafts.
"""

from __future__ import annotations

import json

from core.models import AgentResult, DraftPost, RunContext
from core.text import strip_long_dashes
from .base import BaseAgent, register


@register("founder_voice")
class FounderVoice(BaseAgent):
    def execute(self, ctx: RunContext) -> AgentResult:
        limits = ctx.config.get("limits", {})
        min_conf = float(limits.get("min_confidence_to_publish", 0.5))
        max_posts = int(limits.get("max_posts", 10))

        accepted = [
            r for r in ctx.researched
            if r.verdict == "accepted" and r.confidence >= min_conf
        ]
        accepted.sort(key=lambda r: r.confidence, reverse=True)
        candidates = accepted[:max_posts]

        if not candidates:
            self.log.warning("No high-confidence accepted trends to write about")
            return AgentResult(agent=self.name, ok=True, data=[])

        if self.dry_run(ctx):
            ctx.drafts = [self._sample(r.trend.title) for r in candidates[:max_posts]]
            return AgentResult(agent=self.name, ok=True,
                               data=[d.to_dict() for d in ctx.drafts])

        prompt = self.prompts.get("founder_voice")
        drafts: list[DraftPost] = []
        for r in candidates:
            system, user = prompt.render(
                brand_voice=self.brand(ctx, "brand_voice"),
                purands_context=self.brand(ctx, "purands_context"),
                run_date=ctx.run_date,
                trend=json.dumps(r.to_dict(), ensure_ascii=False, indent=2),
            )
            try:
                d = self.llm.complete_json(system, user)
            except Exception as exc:  # noqa: BLE001 — one bad post shouldn't kill the batch
                self.log.warning("Post generation failed for %r: %s — skipping",
                                 r.trend.title, exc)
                continue
            based_on = list(d.get("based_on", [])) or [r.trend.title]
            drafts.append(DraftPost(
                topic=d.get("topic", r.trend.title),
                body=strip_long_dashes(d.get("body", "")),
                hooks=[strip_long_dashes(h) for h in list(d.get("hooks", []))[:3]],
                cta=strip_long_dashes(d.get("cta", "")),
                hashtags=list(d.get("hashtags", [])),
                based_on=based_on,
            ))

        self.log.info("Wrote %d posts", len(drafts))
        ctx.drafts = drafts
        return AgentResult(agent=self.name, ok=True, data=[d.to_dict() for d in drafts])

    def _sample(self, topic: str) -> DraftPost:
        return DraftPost(
            topic=topic,
            body=f"[DRY-RUN] Sample post body about '{topic}' in founder voice. "
                 "Enable mode: full with an API key to generate a real post.",
            hooks=["Sample hook one.", "Sample hook two.", "Sample hook three."],
            cta="Here's the one thing I'd change first.",
            hashtags=["AI", "retention", "tech"],
            based_on=[topic],
        )
