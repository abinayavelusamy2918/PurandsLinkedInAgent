"""Agent 4 — Engagement Agent.

Reads recent LinkedIn posts about AI / tech (from the `linkedin` source) and
drafts one human-sounding comment per post — up to limits.max_leader_posts
(default 30). Every comment states a clear opinion and NEVER ends with a
question / is never left open-ended.

The real LinkedIn post URL is taken straight from the collected item (not from
the model), so the dashboard always links to the exact post to paste on. Posts
are processed in batches to keep each model response well within token limits.
Attaches CommentSuggestions to ctx.comments.
"""

from __future__ import annotations

import json

from core.models import AgentResult, CommentSuggestion, RunContext
from core.text import strip_long_dashes, strip_trailing_question
from .base import BaseAgent, register

_BATCH_SIZE = 10


@register("engagement_agent")
class EngagementAgent(BaseAgent):
    def execute(self, ctx: RunContext) -> AgentResult:
        limit = int(ctx.config.get("limits", {}).get("max_leader_posts", 30))

        if self.dry_run(ctx):
            ctx.comments = self._samples(limit)
            return AgentResult(agent=self.name, ok=True,
                               data=[c.to_dict() for c in ctx.comments])

        # Prefer real LinkedIn posts; fall back to any collected item only if the
        # linkedin source produced nothing (e.g. disabled / no APIFY_TOKEN).
        linkedin_items = [it for it in ctx.raw_items if it.source == "linkedin"]
        # Draw from the full pool (not just `limit`) so we can backfill toward the
        # target if the model skips any post in a batch.
        pool = linkedin_items or ctx.raw_items

        if not pool:
            self.log.warning(
                "No LinkedIn posts available to engage with — enable the "
                "'linkedin' source in sources.yaml and set APIFY_TOKEN"
            )
            return AgentResult(agent=self.name, ok=True, data=[])

        prompt = self.prompts.get("engagement_agent")
        comments: list[CommentSuggestion] = []

        # Process in batches so no single response gets truncated; stop once we
        # have `limit` comments (each batch draws from distinct posts).
        for start in range(0, len(pool), _BATCH_SIZE):
            if len(comments) >= limit:
                break
            batch = pool[start:start + _BATCH_SIZE]
            leader_posts = json.dumps(
                [
                    {
                        "index": i + 1,
                        "author": it.raw.get("author") or it.source,
                        "posted": it.raw.get("posted_ago", ""),
                        "excerpt": it.summary[:500] or it.title,
                    }
                    for i, it in enumerate(batch)
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
            try:
                data = self.llm.complete_json(system, user)
            except Exception as exc:  # noqa: BLE001 — one bad batch shouldn't kill the rest
                self.log.warning("Comment batch %d failed: %s — skipping",
                                 start // _BATCH_SIZE, exc)
                continue

            for c in (data or []):
                idx = int(c.get("index", 0) or 0) - 1
                if idx < 0 or idx >= len(batch):
                    continue
                item = batch[idx]
                text = strip_trailing_question(strip_long_dashes(c.get("comment", "").strip()))
                if not text:
                    continue
                comments.append(CommentSuggestion(
                    target_author=item.raw.get("author") or item.source,
                    target_post_url=item.url,          # real URL from the source
                    target_excerpt=(item.summary[:200] or item.title),
                    comment=text,
                    angle=c.get("angle", "opinion"),
                    why_it_works=c.get("why_it_works", ""),
                ))

        self.log.info("Drafted %d comments", len(comments))
        ctx.comments = comments[:limit]
        return AgentResult(agent=self.name, ok=True,
                           data=[c.to_dict() for c in ctx.comments])

    def _samples(self, limit: int) -> list[CommentSuggestion]:
        """Realistic dry-run preview so the dashboard layout can be checked
        offline (no APIFY_TOKEN / API key needed)."""
        base = [
            (
                "Dr. Anya Rao",
                "https://www.linkedin.com/posts/example-anya-rao_ai-agents-activity-1",
                "Everyone's shipping AI agents, but almost no one is measuring "
                "whether they actually reduce human workload.",
                "respectful challenge",
                "The deflection rate everyone celebrates hides the real cost: our "
                "own agent deflected 32% of tickets, but the escalations came in "
                "with worse context than a blank form. Handoff quality is the metric "
                "that actually matters, and most dashboards ignore it.",
                "Adds a concrete counter-metric and takes a firm stance — no hedging.",
            ),
            (
                "Marcus Bell",
                "https://www.linkedin.com/posts/example-marcus-bell_llm-cost-activity-2",
                "Most companies don't have an LLM problem, they have a retrieval "
                "problem. Better context beats a bigger model.",
                "expansion",
                "This is exactly right, and the numbers back it up. Swapping to a "
                "smaller model with clean, recent context cut our costs ~40% with no "
                "noticeable quality drop. The real work lives in the data pipeline, "
                "not the model card.",
                "States a clear opinion and reinforces it with a specific outcome.",
            ),
            (
                "Priya Nair",
                "https://www.linkedin.com/posts/example-priya-nair_genai-retention-activity-3",
                "GenAI will transform retention marketing in APAC. WhatsApp + AI "
                "personalization is the next big unlock.",
                "insight",
                "Personalization is the smaller half of this. In APAC the real lever "
                "is timing — a WhatsApp win-back three days after a lapsed order beats "
                "a perfectly worded email a week later. Channel latency, not copy, is "
                "what moves the number.",
                "Takes a definite position and names the underrated factor.",
            ),
        ]
        out: list[CommentSuggestion] = []
        i = 0
        while len(out) < min(limit, 30):
            author, url, excerpt, angle, comment, why = base[i % len(base)]
            n = i + 1
            out.append(CommentSuggestion(
                target_author=author,
                target_post_url=f"{url}{n}",
                target_excerpt=f"[DRY-RUN] {excerpt}",
                comment=comment,
                angle=angle,
                why_it_works=why,
            ))
            i += 1
        return out
