# Purands AI Platform

A modular, production-ready AI content platform for **Purands AI** — an
AI-powered retention marketing company. The first product is a **LinkedIn
content engine** built from six independent AI agents. The architecture is
designed to grow into the central AI operating platform for Purands, supporting
many future agents beyond LinkedIn.

> **Human-in-the-loop by design.** Nothing is auto-posted to LinkedIn and no
> replies are sent automatically. Every run produces review-ready HTML.

---

## Table of contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Folder structure](#folder-structure)
- [How each agent works](#how-each-agent-works)
- [Run it locally](#run-it-locally)
- [Configure data sources](#configure-data-sources)
- [Change prompts & brand voice](#change-prompts--brand-voice)
- [Add a new agent](#add-a-new-agent)
- [GitHub Actions (daily automation)](#github-actions-daily-automation)
- [Secrets](#secrets)
- [Deploy](#deploy)
- [Testing](#testing)

---

## What it does

Once a day (locally or via GitHub Actions), the platform:

1. Collects items from configurable data sources (RSS, news, blogs, GitHub,
   Apify, user URLs).
2. **Finds and ranks** the most important current discussions across AI, SaaS,
   retention marketing, CRM, loyalty, WhatsApp commerce, Shopify, product
   management and the APAC ecosystem.
3. **Verifies** each trend with evidence, statistics, risks, and a confidence
   score — rejecting weak claims.
4. **Writes** a LinkedIn post in a co-founder's voice (plus 3 hooks, a CTA, and
   hashtags).
5. **Drafts value-adding comments** on industry-leader posts.
6. **Produces a review dashboard** (HTML) with a publishing recommendation and
   risk assessment.
7. Separately, **classifies and drafts replies** to comments received on
   Purands' own posts.

Outputs land in `linkedin-agent/output/daily/` and
`linkedin-agent/output/comments/`.

---

## Architecture

Six design decisions drive the whole system (full rationale in
[`ARCHITECTURE.md`](ARCHITECTURE.md)):

| Concern | Approach | Why |
|---------|----------|-----|
| Adding agents | `BaseAgent` + `@register("name")` registry | New agents drop in; orchestrator never changes |
| LLM vendor | `LLMClient` interface, `AnthropicProvider` default | Swap providers by config, not code |
| Data sources | `BaseSource` plugins driven by `sources.yaml` | Never hardcode sources; toggle via YAML |
| Prompts | Markdown files loaded at runtime | Change tone/behaviour with no code change |
| Agent I/O | Typed dataclasses persisted as JSON per run | Decoupled, auditable, re-runnable stages |
| HTML | Jinja2 templates → self-contained files | Presentation separate from logic |

**Pipeline flow:**

```
sources ─► Trend Hunter ─► Research Analyst ─┬─► Founder Voice ──┐
                                             └─► Engagement ─────┤
                                                                 ▼
                                                     Editor & Publisher ─► output/daily/*.html

received comments ─► Comment Reply ─► output/comments/*.html
```

---

## Folder structure

```
purands-ai-platform/
├── README.md                  ← you are here
├── ARCHITECTURE.md            ← decisions & rationale
├── requirements.txt
├── .env.example               ← names of required env vars (no secrets)
├── .github/workflows/
│   └── daily-content.yml      ← daily CI run + commit
└── linkedin-agent/
    ├── config/
    │   ├── config.yaml        ← pipeline, model, paths, mode, limits
    │   └── sources.yaml       ← enable/parameterise data sources
    ├── data/                  ← brand knowledge (markdown, read at runtime)
    │   ├── brand_voice.md
    │   ├── purands_context.md
    │   ├── approved_topics.md
    │   ├── blocked_topics.md
    │   ├── incoming_comments.example.json
    │   └── runs/              ← per-run JSON artifacts
    ├── templates/
    │   ├── prompts/*.md       ← one prompt per agent (never hardcoded)
    │   └── html/*.j2          ← dashboard templates
    ├── core/                  ← config, llm, prompts, models, orchestrator, logging, errors
    ├── agents/                ← the six agents + base/registry
    ├── sources/               ← source plugins + collector
    ├── rendering/             ← Jinja2 HTML renderer
    ├── scripts/               ← run_daily, validate_config, add_agent
    ├── output/{daily,comments}/
    └── tests/
```

> The package directory is `rendering/` (not `html/`) to avoid shadowing
> Python's stdlib `html` module.

---

## How each agent works

Each agent subclasses `BaseAgent`, loads its markdown prompt, fills in brand
voice + the day's data, calls the LLM for **strict JSON**, and maps the result
into typed models on the `RunContext`.

1. **Trend Hunter** (`agents/trend_hunter.py`) — collects raw items, ranks the
   most important discussions. *Discovery only; never writes content.*
2. **Research Analyst** (`research_analyst.py`) — verifies trends, attaches
   evidence/stats/risks + a confidence score, **rejects** weak claims.
3. **Founder Voice** (`founder_voice.py`) — writes one post (+3 hooks, CTA,
   hashtags) from the strongest high-confidence trend, in brand voice.
4. **Engagement Agent** (`engagement_agent.py`) — drafts insightful comments on
   leader posts; explicitly forbidden from "Great post"-style filler.
5. **Editor & Publisher** (`editor_publisher.py`) — editorial assessment +
   renders the daily dashboard. *Never publishes.*
6. **Comment Reply** (`comment_reply.py`) — classifies received comments
   (Question / Sales Lead / Partnership / Spam / …), drafts replies, scores
   leads, renders the comments dashboard. *Never auto-posts.*

---

## Run it locally

Requires Python 3.11+.

```bash
git clone git@github.com:abinayavelusamy2918/Purands_LinkedIn_Agent.git
cd Purands_LinkedIn_Agent
pip install -r requirements.txt
cp .env.example .env          # then add your ANTHROPIC_API_KEY

cd linkedin-agent
python scripts/validate_config.py          # pre-flight checks
python scripts/run_daily.py                # full run (calls the LLM + sources)
# or, no API key / offline, to preview the wiring and HTML:
python scripts/run_daily.py --dry-run
```

Open the newest file in `output/daily/` in a browser. To process received
comments, copy `data/incoming_comments.example.json` to
`data/incoming_comments.json` and edit it.

---

## Configure data sources

Edit `linkedin-agent/config/sources.yaml`. Toggle `enabled`, set params, or add
an entry. **No source is hardcoded in code.** Built-in sources: `rss`, `news`,
`blogs`, `github`, `urls`, `apify`. Replace the placeholder feed URLs with your
own.

---

## Change prompts & brand voice

- **Prompts:** edit the markdown in `templates/prompts/` (e.g.
  `founder_voice.md`). Optional `--- system ---` / `--- user ---` split.
  `{placeholders}` are filled at runtime; unknown ones are left intact.
- **Brand voice & context:** edit the markdown in `data/`
  (`brand_voice.md`, `purands_context.md`, `approved_topics.md`,
  `blocked_topics.md`). These are read on every run — no code change needed.

Set the founder name/persona in `data/purands_context.md`.

---

## Add a new agent

```bash
cd linkedin-agent
python scripts/add_agent.py my_new_agent
```

This scaffolds `agents/my_new_agent.py` and `templates/prompts/my_new_agent.md`.
Then: (1) add `my_new_agent,` to the import list in `agents/__init__.py`, and
(2) add `- my_new_agent` to `pipeline:` in `config/config.yaml`. Done — the
orchestrator picks it up automatically.

---

## GitHub Actions (daily automation)

`.github/workflows/daily-content.yml` runs daily (and on-demand via
**workflow_dispatch**). It checks out the repo, installs deps, validates config,
runs the pipeline using **GitHub Secrets**, and commits the generated dashboards
back to the repo. GitHub is the master copy.

Change the schedule via the `cron` line. Trigger a manual run from the repo's
**Actions** tab → *Daily LinkedIn Content* → *Run workflow*.

---

## Secrets

Set these in **Settings → Secrets and variables → Actions**:

| Secret | Required | Purpose |
|--------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | LLM provider (Claude) |
| `APIFY_TOKEN` | No | Only if the `apify` source is enabled |
| `GITHUB_TOKEN` | Auto | Provided by Actions; raises GitHub API limits |

Never commit real keys. Locally, use a `.env` file (gitignored).

---

## Deploy

Deployment = pushing to GitHub. The daily workflow does the rest. To run on your
own infra instead, schedule `python linkedin-agent/scripts/run_daily.py` with
the same env vars (cron, a container, or any scheduler).

---

## Testing

```bash
cd linkedin-agent
python -m pytest -q
```

Tests cover the prompt loader, source registry/resilience, the agent registry,
and a full **offline** dry-run that renders the dashboards — so CI can verify
wiring without an API key.
