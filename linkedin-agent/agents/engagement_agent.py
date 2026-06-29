"""Agent 4 — Engagement Agent.

Analyses industry-leader posts (drawn from the collected items, or a dedicated
LinkedIn source when configured) and drafts value-adding comments — never
"Great post" filler. Attaches CommentSuggestions to ctx.comments.
"""

from __future__ import annotations

import json

from core.models import AgentResult, CommentSuggestion, RunContext
from .base import BaseAgent, register


@register("engagement_agent")
class EngagementAgent(BaseAgent):
    def execute(self, ctx: RunContext) -> AgentResult:
        # Candidate leader posts: by default we reuse collected items. Swap in a
        # dedicated LinkedIn leader-post source by adding it to sources.yaml.
        candidates = ctx.raw_items[: int(ctx.config.get("limits", {}).get("max_leader_posts", 5))]

        if not candidates:
            self.log.warning("No leader posts available to engage with")
            return AgentResult(agent=self.name, ok=True, data=[])

        if self.dry_run(ctx):
            ctx.comments = [self._sample(candidates[0].title, candidates[0].url)]
            return AgentResult(agent=self.name, ok=True,
                               data=[c.to_dict() for c in ctx.comments])

        prompt = self.prompts.get("engagement_agent")
        leader_posts = json.dumps(
            [{"author": it.source, "url": it.url, "excerpt": it.title + " — " + it.summary[:200]}
             for it in candidates],
            ensure_ascii=False, indent=2,
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
        comments = [
            CommentSuggestion(
                target_author=c.get("target_author", ""),
                target_post_url=c.get("target_post_url", ""),
                target_excerpt=c.get("target_excerpt", ""),
                comment=c.get("comment", ""),
                angle=c.get("angle", "insight"),
                why_it_works=c.get("why_it_works", ""),
            )
            for c in (data or [])
        ]
        ctx.comments = comments
        return AgentResult(agent=self.name, ok=True, data=[c.to_dict() for c in comments])

    def _sample(self, title: str, url: str) -> CommentSuggestion:
        return CommentSuggestion(
            target_author="sample:author",
            target_post_url=url or "https://example.com",
            target_excerpt=title or "Sample leader post",
            comment="[DRY-RUN] A specific, value-adding comment would appear here.",
            angle="insight",
            why_it_works="Sample rationale (dry-run).",
        )
