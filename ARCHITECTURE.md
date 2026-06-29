# Purands AI Platform — Architecture & Build Plan

**Status:** Proposal for approval (no code generated yet)
**Prepared for:** Manoj, Purands AI
**Scope of this document:** System architecture, key decisions, full repository layout, and a file-by-file build plan for the LinkedIn content engine — designed so it grows into the central AI operating platform for Purands AI.


> **Implementation note:** the rendering package ships as `rendering/` (not `html/`) to avoid shadowing Python's stdlib `html` module. Everything else below matches the build.

---

## 1. Guiding principles

These are locked in based on your brief and our decisions:

- **GitHub is the master copy.** All code is committed via the GitHub connector. Local machines are never the source of truth.
- **LLM provider = Anthropic Claude**, behind a provider-agnostic interface so OpenAI/others can be added by config, not code changes.
- **Human-in-the-loop only.** Nothing posts to LinkedIn. No auto-replies. Every output is review-ready HTML.
- **Nothing hardcoded that should be data.** Prompts live in `.md` files. Brand voice lives in `.md` files. Data sources live in config. Python reads them at runtime.
- **Modular and extensible.** Adding a 7th agent (or a non-LinkedIn product) should mean adding files, not rewiring the core.
- **SOLID, logged, error-handled.** Each module has one job; failures are caught, logged, and degrade gracefully.

---

## 2. Key architectural decisions (with recommendations & rationale)

### Decision 1 — Agent base class + registry pattern *(recommended)*
Every agent subclasses a common `BaseAgent` (defines `run(context) -> AgentResult`) and registers itself. The orchestrator discovers and runs agents in a configured pipeline order.

- **Why:** New agents drop in without touching the orchestrator. Enforces a uniform contract (input context, structured output, logging, error handling). This is the single most important choice for "supports many future agents."
- **Alternative considered:** Hardcoded function calls in a script. Rejected — every new agent would require editing orchestration code, violating open/closed.

### Decision 2 — Provider-agnostic LLM client *(recommended)*
A thin `LLMClient` interface with an `AnthropicProvider` implementation. Model name, temperature, and provider are set in `config.yaml`. API key from environment / GitHub Secrets only.

- **Why:** You picked Anthropic now, but the brief says "easy to extend." A one-method interface (`complete(system, prompt) -> str`) means adding OpenAI later is a new file + a config value.
- **Alternative considered:** Call the Anthropic SDK directly throughout. Rejected — couples every agent to one vendor.

### Decision 3 — Source plugin architecture for data collection *(recommended)*
Each data source (Apify, RSS, blog, news, GitHub, user URLs) implements a `BaseSource.fetch() -> list[RawItem]`. Enabled sources and their parameters live in `config/sources.yaml`. The collector loops over enabled sources only.

- **Why:** Directly satisfies "never hardcode sources" and "easily extended." Turn a source on/off or add one via YAML + one class.
- **Alternative considered:** A single fetcher with if/else per source. Rejected — unmaintainable, violates open/closed.

### Decision 4 — Prompt registry loads `.md` at runtime *(recommended)*
A `PromptLoader` reads `templates/` by filename. Agents request prompts by key (e.g., `trend_hunter.system`). Supports simple `{variable}` injection (brand voice, context, today's data).

- **Why:** "Never hardcode prompts." Editing tone/behavior becomes editing markdown — no Python change, no redeploy logic.

### Decision 5 — Structured data contracts between agents *(recommended)*
Agents pass typed objects (dataclasses): `Trend`, `ResearchedTrend`, `DraftPost`, `CommentSuggestion`, `ReplySuggestion`. Persisted as JSON in `data/` per run so any stage can be re-run independently and outputs are auditable.

- **Why:** Decouples agents (Research Analyst doesn't care *how* trends were found), enables re-runs, and gives the Editor a clean object to render.

### Decision 6 — HTML via Jinja2 templates, not string concatenation *(recommended)*
Editor and Reply agents render Jinja2 templates into self-contained HTML (inline CSS/JS, no external build) with nav, tables, color-coded confidence, copy buttons, collapsible sections, source links, responsive layout.

- **Why:** Separates presentation from logic; designers can tweak HTML without touching Python. Self-contained files open anywhere and survive being committed to GitHub.

### Decision 7 — Config-driven orchestration *(recommended)*
`config/config.yaml` defines the run: which agents, in what order, model settings, output paths, run mode (`full` vs `dry-run` with mock data). GitHub Actions just calls `python -m linkedin_agent.run`.

- **Why:** One place to control behavior across local runs and CI.

---

## 3. Repository structure

```
purands-ai-platform/
├── README.md                         # Top-level: what the platform is, how to run
├── ARCHITECTURE.md                   # This document (committed for the team)
├── requirements.txt                  # Pinned Python deps
├── .gitignore
├── .env.example                      # Names of required env vars (no secrets)
│
├── .github/
│   └── workflows/
│       └── daily-content.yml         # Daily CI run: execute agents, commit HTML
│
└── linkedin-agent/
    ├── config/
    │   ├── config.yaml               # Run config: pipeline, model, paths, mode
    │   └── sources.yaml              # Enabled data sources + params (no hardcoding)
    │
    ├── data/                         # Brand knowledge (markdown, read at runtime)
    │   ├── brand_voice.md
    │   ├── purands_context.md
    │   ├── approved_topics.md
    │   ├── blocked_topics.md
    │   └── runs/                     # Per-run JSON artifacts (trends, research, drafts)
    │       └── .gitkeep
    │
    ├── templates/                    # ALL prompts (markdown) + HTML (Jinja2)
    │   ├── prompts/
    │   │   ├── trend_hunter.md
    │   │   ├── research_analyst.md
    │   │   ├── founder_voice.md
    │   │   ├── engagement_agent.md
    │   │   ├── editor_publisher.md
    │   │   └── comment_reply.md
    │   └── html/
    │       ├── dashboard.html.j2     # Editor output (daily review dashboard)
    │       └── comments.html.j2      # Reply agent output
    │
    ├── agents/
    │   ├── __init__.py
    │   ├── base.py                   # BaseAgent contract + registry
    │   ├── trend_hunter.py           # Agent 1
    │   ├── research_analyst.py       # Agent 2
    │   ├── founder_voice.py          # Agent 3
    │   ├── engagement_agent.py       # Agent 4
    │   ├── editor_publisher.py       # Agent 5
    │   └── comment_reply.py          # Agent 6
    │
    ├── core/
    │   ├── __init__.py
    │   ├── config.py                 # Loads + validates config.yaml / sources.yaml
    │   ├── llm.py                    # LLMClient interface + AnthropicProvider
    │   ├── prompts.py                # PromptLoader (reads templates/prompts/*.md)
    │   ├── models.py                 # Dataclasses: Trend, ResearchedTrend, etc.
    │   ├── orchestrator.py           # Builds + runs the agent pipeline
    │   ├── logging_config.py         # Structured logging setup
    │   └── errors.py                 # Custom exceptions
    │
    ├── sources/
    │   ├── __init__.py
    │   ├── base.py                   # BaseSource.fetch() contract + registry
    │   ├── rss_source.py             # RSS feeds
    │   ├── apify_source.py           # Apify actors
    │   ├── blog_source.py            # AI company / tech blogs (HTML/RSS)
    │   ├── news_source.py            # Tech/business news
    │   ├── github_source.py          # Trending GitHub repos
    │   └── url_source.py             # User-supplied URLs
    │
    ├── rendering/
    │   ├── __init__.py
    │   └── renderer.py               # Jinja2 render → self-contained HTML
    │
    ├── scripts/
    │   ├── run_daily.py              # Entry point (also: python -m ...)
    │   ├── add_agent.py              # Scaffolds a new agent from a template
    │   └── validate_config.py        # Pre-flight checks before a run
    │
    ├── output/
    │   ├── daily/                    # Editor dashboards (HTML) — dated files
    │   │   └── .gitkeep
    │   └── comments/                 # Reply agent HTML — dated files
    │       └── .gitkeep
    │
    └── tests/
        ├── test_prompts.py
        ├── test_sources.py
        ├── test_agents_contract.py
        └── test_html_render.py
```

**Note on your brief's tree:** you listed `agents/ data/ scripts/ templates/ output/` and `.github/workflows`. I've kept all of those exactly and added four thin internal packages — `core/`, `sources/`, `html/`, `tests/` — because folding LLM, config, source plugins, and rendering into one place would violate the separation you asked for ("separate data collection, orchestration, HTML generation, utilities, configuration"). If you'd rather keep the top level flatter, I can nest `core/sources/html` under a single `lib/` instead. Flagging before I build.

---

## 4. Data flow (one daily run)

```
                ┌─────────────────────────────────────────────┐
                │ config.yaml + sources.yaml + brand .md files │
                └─────────────────────────────────────────────┘
                                   │ (loaded at startup)
                                   ▼
  sources/* ──► [collector] ──► RawItems
                                   │
                          Agent 1: Trend Hunter      → ranked Trends (no content)
                                   │
                          Agent 2: Research Analyst  → ResearchedTrends (+evidence, confidence, rejects weak)
                                   │
              ┌────────────────────┼─────────────────────┐
              ▼                                           ▼
  Agent 3: Founder Voice                      Agent 4: Engagement Agent
  → DraftPost (post, 3 hooks, CTA, tags)      → CommentSuggestions on leader posts
              └────────────────────┬─────────────────────┘
                                   ▼
                          Agent 5: Editor & Publisher
                          → output/daily/YYYY-MM-DD.html (review dashboard)

  (separate trigger / inputs)
  received comments ──► Agent 6: Comment Reply ──► output/comments/YYYY-MM-DD.html
```

Each stage writes its JSON to `data/runs/YYYY-MM-DD/` so stages are independently re-runnable and auditable.

---

## 5. Agent specifications

| # | Agent | Input | Output | Must NOT do |
|---|-------|-------|--------|-------------|
| 1 | **Trend Hunter** | RawItems from sources | Ranked `Trend` list across APAC/AI/SaaS/retention/CRM/loyalty/WhatsApp/Shopify/PM/startups | Generate content |
| 2 | **Research Analyst** | Trends | `ResearchedTrend` (evidence, stats, examples, recent news, risks, confidence score); weak claims rejected | Accept unsupported claims |
| 3 | **Founder Voice** | Top researched trends + brand voice | `DraftPost`: full post, 3 alt hooks, CTA, hashtags | Sound AI-generated, use clichés/fluff/hype |
| 4 | **Engagement Agent** | Industry-leader posts | `CommentSuggestion[]`: insightful comments that add value, challenge, expand, or ask | Write "Great post" / "Thanks for sharing" |
| 5 | **Editor & Publisher** | All of the above | Review dashboard HTML in `output/daily/` | Auto-publish |
| 6 | **Comment Reply** | Comments received on Purands posts | Classify (Question/Agreement/Objection/Sales Lead/Partnership/Support/Spam/Ignore) + suggested reply, why it works, follow-up, lead score → HTML in `output/comments/` | Auto-post replies |

The Editor dashboard includes exactly the sections you specified: Today's Trends, Research Summary, LinkedIn Post, Alternative Hooks, Suggested Comments, Evidence Sources, Confidence Scores, Publishing Recommendation, Risk Assessment.

---

## 6. GitHub Actions workflow (`daily-content.yml`)

Triggers: `schedule` (daily cron) + `workflow_dispatch` (manual). Steps:

1. Checkout repo (the master copy).
2. Set up Python, install `requirements.txt`.
3. Inject secrets as env vars (`ANTHROPIC_API_KEY`, `APIFY_TOKEN`, etc. — **GitHub Secrets only**).
4. Run `python -m linkedin_agent.run` → executes the configured pipeline, reads prompts/brand files, generates HTML.
5. Commit new files in `output/daily/` and `output/comments/` back to the repo (bot commit).

**Required GitHub Secrets:** `ANTHROPIC_API_KEY` (required), `APIFY_TOKEN` (optional, only if Apify source enabled). Documented in README and `.env.example`.

---

## 7. What I need from you to start the build pass

1. **GitHub connector connected** + the **repo** to write to (`owner/name`). Is `purands-ai-platform` an existing repo, or should I create it? (The GitHub commit tools aren't live in this session yet — they came up as "still connecting.")
2. **Co-founder identity for the Founder Voice agent** — first name / persona to write as (improves authenticity; can be a placeholder you edit later).
3. **Confirm the folder layout** in §3 (full tree vs. flatter `lib/` variant).

---

## 8. Build sequencing (next passes, once approved)

1. **Foundation:** repo scaffold, `requirements.txt`, config + loaders, `core/` (llm, prompts, models, logging, errors), `BaseAgent`, `BaseSource`.
2. **Sources + collector:** RSS + user-URL sources working end-to-end; others stubbed and config-gated.
3. **Agents 1–3 + Editor:** trend hunting → research → founder post → daily dashboard HTML (runs end-to-end with real LLM, mock sources if needed).
4. **Agents 4 & 6:** engagement comments + comment reply, with their HTML.
5. **GitHub Actions + README + tests:** CI workflow, full docs, contract tests.

Each pass: I tell you which files I'm creating before I create them, never overwrite without asking, and explain any non-obvious decision.
