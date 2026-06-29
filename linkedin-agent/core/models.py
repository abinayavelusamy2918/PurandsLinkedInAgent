"""Shared data contracts passed between agents.

These dataclasses are the *interface* between pipeline stages. The Research
Analyst doesn't care how a Trend was discovered; it only consumes `Trend`
objects. Each is JSON-serialisable so a run can be persisted to data/runs/ and
any stage re-run independently.

Design note: we keep these deliberately plain (stdlib dataclasses, no pydantic)
to minimise dependencies. `to_dict`/`from_dict` give us round-tripping for the
run artifacts and for feeding objects into Jinja2 templates.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Source layer
# --------------------------------------------------------------------------- #
@dataclass
class RawItem:
    """A single raw item pulled from a data source before any analysis."""

    title: str
    url: str
    source: str                      # which source produced it (e.g. "rss:techcrunch")
    summary: str = ""
    published: str = ""              # ISO date string if available
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Agent 1 — Trend Hunter
# --------------------------------------------------------------------------- #
@dataclass
class Trend:
    """A ranked, important discussion. NO generated content — discovery only."""

    title: str
    category: str                    # e.g. "Retention Marketing", "WhatsApp Commerce"
    rank: int                        # 1 = most important
    rationale: str                   # why it matters now
    signals: list[str] = field(default_factory=list)   # what makes it notable
    sources: list[str] = field(default_factory=list)   # supporting URLs
    region: str = "APAC"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Agent 2 — Research Analyst
# --------------------------------------------------------------------------- #
@dataclass
class Evidence:
    claim: str
    support: str                     # statistic / example / news that backs it
    url: str = ""


@dataclass
class ResearchedTrend:
    """A verified trend. Weak/unsupported trends are dropped before this stage."""

    trend: Trend
    confidence: float                # 0.0 - 1.0
    evidence: list[Evidence] = field(default_factory=list)
    statistics: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    recent_news: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    verdict: str = "accepted"        # "accepted" | "rejected"
    reject_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


# --------------------------------------------------------------------------- #
# Agent 3 — Founder Voice
# --------------------------------------------------------------------------- #
@dataclass
class DraftPost:
    """A review-ready LinkedIn post written in the co-founder's voice."""

    topic: str
    body: str
    hooks: list[str] = field(default_factory=list)   # exactly 3 alternatives
    cta: str = ""
    hashtags: list[str] = field(default_factory=list)
    based_on: list[str] = field(default_factory=list)  # trend titles used

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Agent 4 — Engagement Agent
# --------------------------------------------------------------------------- #
@dataclass
class CommentSuggestion:
    """A value-adding comment on an industry leader's post."""

    target_author: str
    target_post_url: str
    target_excerpt: str
    comment: str
    angle: str                       # "insight" | "respectful challenge" | "question" | "expansion"
    why_it_works: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Agent 6 — Comment Reply
# --------------------------------------------------------------------------- #
class CommentClass(str, Enum):
    QUESTION = "Question"
    AGREEMENT = "Agreement"
    OBJECTION = "Objection"
    SALES_LEAD = "Sales Lead"
    PARTNERSHIP = "Partnership Opportunity"
    SUPPORT = "Customer Support"
    SPAM = "Spam"
    IGNORE = "Ignore"


@dataclass
class ReplySuggestion:
    """A suggested reply to a comment received on a Purands post. Never auto-posted."""

    original_comment: str
    commenter: str
    classification: str              # one of CommentClass values
    suggested_reply: str
    why_it_works: str
    follow_up: str = ""
    lead_score: int = 0              # 0-100; meaningful for Sales Lead / Partnership

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Agent result envelope + run context
# --------------------------------------------------------------------------- #
@dataclass
class AgentResult:
    """Uniform return type for every agent's run()."""

    agent: str
    ok: bool
    data: Any = None                 # the agent's typed payload
    error: str = ""
    started_at: str = field(default_factory=_now_iso)
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # `data` may itself contain dataclasses; asdict handles nested ones.
        return d


@dataclass
class RunContext:
    """Carried through the whole pipeline. Agents read what they need and
    attach their outputs so downstream agents (and the Editor) can use them."""

    run_date: str
    config: dict[str, Any]
    brand: dict[str, str] = field(default_factory=dict)   # brand .md contents by name
    raw_items: list[RawItem] = field(default_factory=list)
    trends: list[Trend] = field(default_factory=list)
    researched: list[ResearchedTrend] = field(default_factory=list)
    drafts: list[DraftPost] = field(default_factory=list)
    comments: list[CommentSuggestion] = field(default_factory=list)
    replies: list[ReplySuggestion] = field(default_factory=list)
    results: list[AgentResult] = field(default_factory=list)
