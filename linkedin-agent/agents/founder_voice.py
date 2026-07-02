"""Agent 3 — Founder Voice.

Writes LinkedIn posts in a Purands AI co-founder's voice — ONE post per accepted,
high-confidence trend, up to limits.max_posts (default 10).

Posts that can be tied to Purands are PRIORITISED: each trend is first classified
for Purands relevance. Relevant trends are ordered first and written as
"how Purands solves this" posts (product-led, showcasing Purands capabilities
against the business problem). The remaining trends stay as normal practitioner
posts. Each DraftPost records the trend it was based on (for the research view)
and whether it is a Purands-tied post. Attaches the list to ctx.drafts.
"""

from __future__ import annotations

import json

from core.models import AgentResult, DraftPost, RunContext
from core.text import strip_long_dashes
from .base import BaseAgent, register

_SOLUTION_DIRECTIVE = (
    "This trend connects directly to Purands AI. Make this post PRIMARILY about "
    "how Purands solves the business problem the trend surfaces. Name the problem, "
    "then show concretely which Purands capabilities address it (AI retention "
    "agents on top of CRM/CDP and WhatsApp/Shopify messaging: win-back, "
    "replenishment, abandoned-cart, churn prediction, loyalty/VIP) and the "
    "measurable outcome. Write as a founder explaining how they would solve it: "
    "credible and specific, never salesy or hypey. Purands angle: {angle}"
)
_NORMAL_DIRECTIVE = (
    "This trend is general AI/tech and not a direct fit for Purands. Write a "
    "genuine practitioner point of view on it. Do NOT force-mention Purands or "
    "pitch the product."
)


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

        if not accepted:
            self.log.warning("No high-confidence accepted trends to write about")
            return AgentResult(agent=self.name, ok=True, data=[])

        if self.dry_run(ctx):
            ctx.drafts = [self._sample(r.trend.title, i == 0)
                          for i, r in enumerate(accepted[:max_posts])]
            return AgentResult(agent=self.name, ok=True,
                               data=[d.to_dict() for d in ctx.drafts])

        # 1) Classify each trend for Purands relevance (one call).
        tie = self._classify(ctx, accepted)

        # 2) Prioritise Purands-relevant trends first, then the rest (each already
        #    confidence-sorted). Take the top max_posts.
        relevant = [r for r in accepted if tie.get(r.trend.title, {}).get("relevant")]
        others = [r for r in accepted if not tie.get(r.trend.title, {}).get("relevant")]
        candidates = (relevant + others)[:max_posts]
        self.log.info("Post priority: %d Purands-tied, %d general (of %d accepted)",
                      len([r for r in candidates if r in relevant]),
                      len([r for r in candidates if r in others]), len(accepted))

        # 3) Generate one post per trend with the right directive.
        prompt = self.prompts.get("founder_voice")
        drafts: list[DraftPost] = []
        for r in candidates:
            info = tie.get(r.trend.title, {})
            is_tie = bool(info.get("relevant"))
            directive = (_SOLUTION_DIRECTIVE.format(angle=info.get("angle", ""))
                         if is_tie else _NORMAL_DIRECTIVE)
            system, user = prompt.render(
                brand_voice=self.brand(ctx, "brand_voice"),
                purands_context=self.brand(ctx, "purands_context"),
                purands_directive=directive,
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
                purands_tie=is_tie,
            ))

        # Keep Purands-tied posts first (high priority) in the final order.
        drafts.sort(key=lambda d: not d.purands_tie)
        self.log.info("Wrote %d posts (%d Purands-tied)",
                      len(drafts), sum(1 for d in drafts if d.purands_tie))
        ctx.drafts = drafts
        return AgentResult(agent=self.name, ok=True, data=[d.to_dict() for d in drafts])

    def _classify(self, ctx: RunContext, accepted) -> dict[str, dict]:
        """Return {trend_title: {"relevant": bool, "angle": str}}."""
        try:
            prompt = self.prompts.get("purands_classifier")
            trends = [
                {"title": r.trend.title, "category": r.trend.category,
                 "rationale": r.trend.rationale}
                for r in accepted
            ]
            system, user = prompt.render(
                purands_context=self.brand(ctx, "purands_context"),
                trends=json.dumps(trends, ensure_ascii=False, indent=2),
            )
            data = self.llm.complete_json(system, user)
            out = {}
            for c in (data or []):
                title = c.get("title", "")
                if title:
                    out[title] = {"relevant": bool(c.get("relevant")),
                                  "angle": c.get("angle", "")}
            return out
        except Exception as exc:  # noqa: BLE001 — fall back to all-general on failure
            self.log.warning("Purands classification failed: %s — treating all as general", exc)
            return {}

    def _sample(self, topic: str, tie: bool) -> DraftPost:
        return DraftPost(
            topic=topic,
            body=f"[DRY-RUN] Sample post body about '{topic}' in founder voice. "
                 "Enable mode: full with an API key to generate a real post.",
            hooks=["Sample hook one.", "Sample hook two.", "Sample hook three."],
            cta="Here's the one thing I'd change first.",
            hashtags=["AI", "retention", "tech"],
            based_on=[topic],
            purands_tie=tie,
        )
