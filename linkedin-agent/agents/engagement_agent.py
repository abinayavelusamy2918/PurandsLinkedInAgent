"""Agent 4 — Engagement Agent.

Reads recent LinkedIn posts about AI / tech (from the `linkedin` source) and
drafts one human-sounding, value-adding comment per post — never "Great post"
filler. Limited to the top N posts per day (config: limits.max_leader_posts).

The real LinkedIn post URL is taken straight from the collected item (not from
the model), so the dashboard always links to the exact post you should navigate
to and paste the comment on. Attaches CommentSuggestions to ctx.comments.
"""

from __future__ import annotations

import json

from core.models import AgentResult, CommentSuggestion, RunContext
from .base import BaseAgent, register


@register("engagement_agent")
class EngagementAgent(BaseAgent):
    def execute(self, ctx: RunContext) -> AgentResult:
        limit = int(ctx.config.get("limits", {}).get("max_leader_posts", 5))

        if self.dry_run(ctx):
            ctx.comments = self._samples(limit)
            return AgentResult(agent=self.name, ok=True,
                               data=[c.to_dict() for c in ctx.comments])

        # Prefer real LinkedIn posts; fall back to any collected item only if the
        # linkedin source produced nothing (e.g. disabled / no APIFY_TOKEN).
        linkedin_items = [it for it in ctx.raw_items if it.source == "linkedin"]
        candidates = (linkedin_items or ctx.raw_items)[:limit]

        if not candidates:
            self.log.warning(
                "No LinkedIn posts available to engage with — enable the "
                "'linkedin' source in sources.yaml and set APIFY_TOKEN"
            )
            return AgentResult(agent=self.name, ok=True, data=[])

        prompt = self.prompts.get("engagement_agent")
        # Number the posts so the model refers to them by index; we map its
        # comments back to the real URL/author ourselves.
        leader_posts = json.dumps(
            [
                {
                    "index": i + 1,
                    "author": it.raw.get("author") or it.source,
                    "posted": it.raw.get("posted_ago", ""),
                    "excerpt": it.summary[:500] or it.title,
                }
                for i, it in enumerate(candidates)
            ],
            ensure_ascii=False,
            indent=2,
        )
        system, user = prompt.render(
            brand_voice=self.brand(ctx, "brand_voice"),
            purands_context=self.brand(ctx, "purands_context"),
            approved_topics=self.brand(ctx, "approved_topics"),
            blocked_topics=self.brand(ctx, "blocked_topics"),
            run_date=ctx.run_date,
            leader_posts=leader_posts,
        )
        data = self.llm.complete_json(system, user)

        comments: list[CommentSuggestion] = []
        for c in (data or []):
            idx = int(c.get("index", 0) or 0) - 1
            if idx < 0 or idx >= len(candidates):
                continue
            item = candidates[idx]
            comments.append(CommentSuggestion(
                target_author=item.raw.get("author") or item.source,
                target_post_url=item.url,          # real URL from the source
                target_excerpt=(item.summary[:200] or item.title),
                comment=c.get("comment", ""),
                angle=c.get("angle", "insight"),
                why_it_works=c.get("why_it_works", ""),
            ))

        ctx.comments = comments[:limit]
        return AgentResult(agent=self.name, ok=True,
                           data=[c.to_dict() for c in ctx.comments])

    def _samples(self, limit: int) -> list[CommentSuggestion]:
        """Realistic dry-run preview so the dashboard layout can be checked
        offline (no APIFY_TOKEN / API key needed)."""
        posts = [
            (
                "Dr. Anya Rao",
                "https://www.linkedin.com/posts/example-anya-rao_ai-agents-activity-1",
                "Everyone's shipping AI agents, but almost no one is measuring "
                "whether they actually reduce human workload. Adoption != value.",
                "respectful challenge",
                "We ran the numbers on our own support agent: it deflected 32% of "
                "tickets but the 68% it escalated came with worse context than a "
                "blank form. Deflection rate hid a real handoff-quality problem. "
                "How are you measuring the escalations, not just the wins?",
                "Adds a concrete counter-metric (handoff quality) and asks a sharp "
                "follow-up — reads like a practitioner, not a brand.",
            ),
            (
                "Marcus Bell",
                "https://www.linkedin.com/posts/example-marcus-bell_llm-cost-activity-2",
                "Hot take: most companies don't have an LLM problem, they have a "
                "retrieval problem. Better context beats a bigger model.",
                "expansion",
                "This matches what we saw — swapping to a smaller model with clean, "
                "recent context cut our costs ~40% and users didn't notice a quality "
                "drop. The unglamorous work is in the data pipeline, not the model card.",
                "Agrees with a specific number and extends the point to where the real "
                "effort lives; conversational and credible.",
            ),
            (
                "Priya Nair",
                "https://www.linkedin.com/posts/example-priya-nair_genai-retention-activity-3",
                "GenAI is going to transform retention marketing in APAC. WhatsApp "
                "+ AI personalization is the next big unlock.",
                "insight",
                "The unlock in APAC is less about personalization and more about "
                "timing — a win-back on WhatsApp 3 days after a lapsed order beats a "
                "perfectly worded email a week later. Channel latency is the lever "
                "people underrate.",
                "Introduces a non-obvious angle (channel latency) grounded in the "
                "region; specific and human.",
            ),
            (
                "Tom Okafor",
                "https://www.linkedin.com/posts/example-tom-okafor_ai-startups-activity-4",
                "Every AI startup pitch this week: 'we're building the agent layer.' "
                "What does that even mean anymore?",
                "question",
                "Genuinely curious — when you hear 'agent layer,' do you read it as "
                "orchestration, memory, or just a wrapper with tools bolted on? The "
                "term seems to mean whichever part the founder happens to own.",
                "A real, thoughtful question that advances the thread instead of "
                "piling on; invites the author to define terms.",
            ),
            (
                "Lena Fischer",
                "https://www.linkedin.com/posts/example-lena-fischer_machine-learning-activity-5",
                "Reminder: your model is only as good as the feedback loop around it. "
                "Most teams ship the model and forget the loop.",
                "expansion",
                "The loop is also where trust is won or lost — we started showing "
                "users *why* a recommendation changed after their feedback, and "
                "correction rates dropped because people stopped fighting the system. "
                "Closing the loop visibly matters as much as closing it technically.",
                "Builds on the author's point with a specific, believable outcome; "
                "sounds like shared experience, not marketing.",
            ),
        ]
        out = []
        for author, url, excerpt, angle, comment, why in posts[:limit]:
            out.append(CommentSuggestion(
                target_author=author,
                target_post_url=url,
                target_excerpt=f"[DRY-RUN] {excerpt}",
                comment=comment,
                angle=angle,
                why_it_works=why,
            ))
        return out
