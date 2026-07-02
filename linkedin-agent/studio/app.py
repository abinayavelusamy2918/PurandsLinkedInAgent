#!/usr/bin/env python3
"""Purands AI — Comment Studio (permanent, interactive tool).

Paste a LinkedIn post URL and get ONE human, opinion-only comment (never a
question, no long dashes). For any statistic the comment cites, it runs a real
web search and shows the source link collapsibly under the comment so you can
verify it before posting.

This tool is standalone and is NOT part of the daily regeneration. It lives in
the repo permanently.

Run:
    cd linkedin-agent
    ../.venv/bin/python studio/app.py
    # then open http://localhost:5000 in your browser

Requires OPENAI_API_KEY and APIFY_TOKEN in .env (same as the daily pipeline).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make the linkedin-agent package root importable regardless of CWD.
PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG_ROOT))


def _load_dotenv() -> None:
    env_file = PKG_ROOT.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()

import requests  # noqa: E402
from flask import Flask, Response, jsonify, render_template, request  # noqa: E402

from core.config import load_settings, require_env  # noqa: E402
from core.llm import build_llm  # noqa: E402
from core.text import strip_long_dashes, strip_trailing_question  # noqa: E402

APIFY_POST_ACTOR = "apimaestro/linkedin-post-detail"
APIFY_SEARCH_ACTOR = "apify/rag-web-browser"

app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))

# LLM is built lazily on first use so the web app boots even before a request
# (and so a missing key surfaces as a clean error, not a boot crash).
_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = build_llm(load_settings().llm, mode="full")
    return _llm


# Optional password protection (recommended when hosted publicly). If
# STUDIO_PASSWORD is set, the whole app requires HTTP Basic auth.
_STUDIO_USER = os.getenv("STUDIO_USER", "purands")
_STUDIO_PASSWORD = os.getenv("STUDIO_PASSWORD")


@app.before_request
def _require_auth():
    if not _STUDIO_PASSWORD:
        return None  # no password configured -> open
    auth = request.authorization
    if not auth or auth.username != _STUDIO_USER or auth.password != _STUDIO_PASSWORD:
        return Response(
            "Authentication required.", 401,
            {"WWW-Authenticate": 'Basic realm="Purands Comment Studio"'},
        )
    return None

_SYSTEM = (
    "You draft ONE LinkedIn comment as a real person who works at Purands AI "
    "(an AI retention-marketing company). The comment must read like a "
    "knowledgeable human, not a brand.\n\n"
    "Rules:\n"
    "- First person, natural, specific to THIS post. Reference something concrete "
    "from it so it could not be pasted on any other post.\n"
    "- STATE A CLEAR OPINION. Never end with a question. No question marks at the "
    "end, ideally none at all. Do not be open-ended.\n"
    "- ADD YOUR OWN PERSPECTIVE, do not just agree with or restate the post. "
    "Contribute something new: a supplementary point, a different angle, or an "
    "insight the post did not make. A brief nod to the post is fine, but the value "
    "must be what you add on top, not praise or repetition.\n"
    "- NEVER use long dashes (em dash or en dash). Use commas, periods, or a short "
    "hyphen.\n"
    "- No hashtags, no links, no selling, at most one emoji only if natural.\n"
    "- 1 to 4 sentences.\n"
    "- If (and only if) you cite a statistic or a specific factual claim, list it "
    "in \"stats\" with a concrete web \"search_query\" someone could use to find "
    "the source. If you cite nothing factual, return an empty stats list.\n\n"
    "Return STRICT JSON with keys: \"comment\", \"angle\" (one of \"insight\", "
    "\"respectful challenge\", \"expansion\", \"opinion\"), \"why_it_works\", "
    "\"stats\" (list of objects with \"claim\" and \"search_query\"). "
    "No prose outside the JSON."
)


def _apify_run(actor_id: str, run_input: dict, *, limit: int = 5, timeout: int = 120):
    token = require_env("APIFY_TOKEN")
    endpoint = (
        f"https://api.apify.com/v2/acts/{actor_id.replace('/', '~')}"
        f"/run-sync-get-dataset-items?token={token}&limit={limit}"
    )
    resp = requests.post(endpoint, json=run_input, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _scrape_post(url: str) -> dict | None:
    recs = _apify_run(APIFY_POST_ACTOR, {"post_urls": [url]}, limit=1)
    if not recs:
        return None
    r = recs[0] if isinstance(recs[0], dict) else {}
    post = r.get("post") or {}
    author = r.get("author") or {}
    return {
        "text": (post.get("text") or "").strip(),
        "author": author.get("name") or "",
        "headline": author.get("headline") or "",
        "url": post.get("url") or url,
    }


def _generate_comment(post: dict) -> dict:
    user = (
        f"LinkedIn post by {post['author']}"
        f"{' (' + post['headline'] + ')' if post['headline'] else ''}:\n\n"
        f"{post['text']}\n\n"
        "Write one strong, human comment stating a clear opinion. Do not end with "
        "a question."
    )
    return _get_llm().complete_json(_SYSTEM, user) or {}


def _search_source(query: str) -> dict | None:
    recs = _apify_run(
        APIFY_SEARCH_ACTOR,
        {"query": query, "maxResults": 2, "outputFormats": ["markdown"]},
        limit=2, timeout=60,
    )
    for rec in recs:
        if not isinstance(rec, dict):
            continue
        md = rec.get("metadata") or {}
        url = md.get("url") or rec.get("url") or (rec.get("crawl") or {}).get("loadedUrl")
        title = md.get("title") or url
        if url:
            return {"url": url, "title": title}
    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/daily")
def daily():
    """Serve today's (the latest) generated daily dashboard. Only the present
    day is shown here; older dashboards remain in the repo archive."""
    out_dir = PKG_ROOT / "output" / "daily"
    files = [p for p in out_dir.glob("*.html")] if out_dir.exists() else []
    if not files:
        return (
            "<body style='font-family:sans-serif;background:#0f1115;color:#e8eaed;"
            "padding:40px'><h2>No daily dashboard yet</h2><p>The daily run hasn't "
            "produced a dashboard on this deploy. It appears after the next daily "
            "GitHub Action run.</p><p><a style='color:#4f8cff' href='/'>&larr; "
            "Comment Studio</a></p></body>", 404,
        )
    latest = max(files, key=lambda p: p.stem)  # filenames are YYYY-MM-DD
    return latest.read_text(encoding="utf-8")


@app.route("/analyze", methods=["POST"])
def analyze():
    url = ((request.json or {}).get("url") or "").strip()
    if not url:
        return jsonify({"error": "Please paste a LinkedIn post URL."}), 400
    if "linkedin.com" not in url:
        return jsonify({"error": "That doesn't look like a LinkedIn URL."}), 400

    try:
        post = _scrape_post(url)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Could not fetch the post: {exc}"}), 502
    if not post or not post["text"]:
        return jsonify({"error": "No post text found. Make sure it's a public LinkedIn post URL."}), 404

    try:
        result = _generate_comment(post)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Comment generation failed: {exc}"}), 500

    comment = strip_trailing_question(strip_long_dashes((result.get("comment") or "").strip()))

    # Enrich each cited stat with a real source link (best-effort).
    sources = []
    for stat in (result.get("stats") or []):
        claim = stat.get("claim", "")
        query = stat.get("search_query") or claim
        src = None
        if query:
            try:
                src = _search_source(query)
            except Exception:  # noqa: BLE001 — a failed search shouldn't break the response
                src = None
        sources.append({"claim": claim, "source": src})

    return jsonify({
        "post": post,
        "comment": comment,
        "angle": result.get("angle", "opinion"),
        "why": result.get("why_it_works", ""),
        "sources": sources,
    })


if __name__ == "__main__":
    port = int(os.getenv("STUDIO_PORT", "5000"))
    print(f"\n  Purands AI Comment Studio → http://localhost:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
