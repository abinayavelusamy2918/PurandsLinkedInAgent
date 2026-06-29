"""Agent 6 — Comment Reply.

Reads comments received on Purands' own posts (from data/incoming_comments.json),
classifies each, drafts a suggested reply, explains why it works, suggests a
follow-up, and scores leads. Renders an HTML review file in output/comments/.
NEVER auto-posts.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.config import PACKAGE_ROOT
from core.models import AgentResult, ReplySuggestion, RunContext
from rendering.renderer import render_comments
from .base import BaseAgent, register

INCOMING = PACKAGE_ROOT / "data" / "incoming_comments.json"


@register("comment_reply")
class CommentReply(BaseAgent):
    def execute(self, ctx: RunContext) -> AgentResult:
        comments = _load_incoming()
        if not comments:
            self.log.info("No incoming comments found at %s — nothing to do", INCOMING)
            return AgentResult(agent=self.name, ok=True, data=[])

        if self.dry_run(ctx):
            ctx.replies = [self._sample(c) for c in comments]
        else:
            prompt = self.prompts.get("comment_reply")
            system, user = prompt.render(
                brand_voice=self.brand(ctx, "brand_voice"),
                purands_context=self.brand(ctx, "purands_context"),
                run_date=ctx.run_date,
                comments=json.dumps(comments, ensure_ascii=False, indent=2),
            )
            data = self.llm.complete_json(system, user)
            ctx.replies = [_to_reply(d) for d in (data or [])]

        # Render the comments review HTML.
        out_dir = Path(ctx.config.get("paths", {}).get("output_comments", "output/comments"))
        out_path = render_comments(ctx, PACKAGE_ROOT / out_dir)
        self.log.info("Wrote comments dashboard: %s", out_path)
        return AgentResult(agent=self.name, ok=True,
                           data={"replies": [r.to_dict() for r in ctx.replies],
                                 "html": str(out_path)})

    def _sample(self, c: dict) -> ReplySuggestion:
        return ReplySuggestion(
            original_comment=c.get("comment", ""),
            commenter=c.get("commenter", "unknown"),
            classification="Question",
            suggested_reply="[DRY-RUN] A specific, helpful reply would appear here.",
            why_it_works="Sample rationale (dry-run).",
            follow_up="None",
            lead_score=10,
        )


def _load_incoming() -> list[dict]:
    if not INCOMING.exists():
        return []
    try:
        data = json.loads(INCOMING.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else data.get("comments", [])


def _to_reply(d: dict) -> ReplySuggestion:
    return ReplySuggestion(
        original_comment=d.get("original_comment", ""),
        commenter=d.get("commenter", ""),
        classification=d.get("classification", "Ignore"),
        suggested_reply=d.get("suggested_reply", ""),
        why_it_works=d.get("why_it_works", ""),
        follow_up=d.get("follow_up", ""),
        lead_score=int(d.get("lead_score", 0) or 0),
    )
