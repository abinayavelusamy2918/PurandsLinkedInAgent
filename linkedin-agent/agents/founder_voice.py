"""Agent 3 — Founder Voice.

Writes a LinkedIn post in a Purands AI co-founder's voice from the strongest
accepted, high-confidence trend. Produces the post body, three alternative
hooks, a CTA, and hashtags. Attaches a DraftPost to ctx.drafts.
"""

from __future__ import annotations

import json

from core.models import AgentResult, DraftPost, RunContext
from .base import BaseAgent, register


@register("founder_voice")
class FounderVoice(BaseAgent):
    def execute(self, ctx: RunContext) -> AgentResult:
        limits = ctx.config.get("limits", {})
        min_conf = float(limits.get("min_confidence_to_publish", 0.6))
        top_n = int(limits.get("max_researched_for_posts", 3))

        accepted = [
            r for r in ctx.researched
            if r.verdict == "accepted" and r.confidence >= min_conf
        ]
        accepted.sort(key=lambda r: r.confidence, reverse=True)
        candidates = accepted[:top_n]

        if not candidates:
            self.log.warning("No high-confidence accepted trends to write about")
            return AgentResult(agent=self.name, ok=True, data=[])

        if self.dry_run(ctx):
            ctx.drafts = [self._sample(candidates[0].trend.title)]
            return AgentResult(agent=self.name, ok=True,
                               data=[d.to_dict() for d in ctx.drafts])

        prompt = self.prompts.get("founder_voice")
        system, user = prompt.render(
            brand_voice=self.brand(ctx, "brand_voice"),
            purands_context=self.brand(ctx, "purands_context"),
            run_date=ctx.run_date,
            researched=json.dumps([r.to_dict() for r in candidates], ensure_ascii=False, indent=2),
        )
        d = self.llm.complete_json(system, user)
        draft = DraftPost(
            topic=d.get("topic", ""),
            body=d.get("body", ""),
            hooks=list(d.get("hooks", []))[:3],
            cta=d.get("cta", ""),
            hashtags=list(d.get("hashtags", [])),
            based_on=list(d.get("based_on", [])),
        )
        ctx.drafts = [draft]
        return AgentResult(agent=self.name, ok=True, data=[draft.to_dict()])

    def _sample(self, topic: str) -> DraftPost:
        return DraftPost(
            topic=topic,
            body="[DRY-RUN] Sample post body in founder voice. Enable mode: full "
                 "with an API key to generate a real post.",
            hooks=["Sample hook one.", "Sample hook two.", "Sample hook three."],
            cta="What's worked for your team?",
            hashtags=["retention", "whatsappcommerce", "loyalty"],
            based_on=[topic],
        )
