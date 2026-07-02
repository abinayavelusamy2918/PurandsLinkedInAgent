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
import re
import sys
from html import escape
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
from flask import Flask, Response, jsonify, render_template, request, send_from_directory  # noqa: E402

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


_DAILY_DIR = PKG_ROOT / "output" / "daily"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _daily_dates() -> list[str]:
    """All available dashboard dates (YYYY-MM-DD), newest first."""
    if not _DAILY_DIR.exists():
        return []
    return sorted((p.stem for p in _DAILY_DIR.glob("*.html") if _DATE_RE.match(p.stem)),
                  reverse=True)


def _read_dashboard(path: Path) -> str:
    """Read a dashboard and make its asset links absolute (/assets/...), so images
    resolve no matter which route depth served the page (/daily or /daily/<date>)."""
    html = path.read_text(encoding="utf-8")
    return html.replace('src="assets/', 'src="/assets/').replace('href="assets/', 'href="/assets/')


def _no_dashboard(msg: str):
    return (
        "<body style='font-family:sans-serif;background:#0f1115;color:#e8eaed;"
        f"padding:40px'><h2>{escape(msg)}</h2><p><a style='color:#7C5CFC' "
        "href='/archive'>&larr; Archive</a> · <a style='color:#7C5CFC' href='/'>"
        "Comment Studio</a></p></body>", 404,
    )


@app.route("/daily")
def daily():
    """Serve today's (the latest) generated daily dashboard."""
    dates = _daily_dates()
    if not dates:
        return _no_dashboard("No daily dashboard yet")
    return _read_dashboard(_DAILY_DIR / f"{dates[0]}.html")


@app.route("/daily/<date>")
def daily_date(date: str):
    """Serve a specific day's dashboard from the archive."""
    if not _DATE_RE.match(date):
        return _no_dashboard("Invalid date")
    f = _DAILY_DIR / f"{date}.html"
    if not f.exists():
        return _no_dashboard(f"No dashboard for {date}")
    return _read_dashboard(f)


@app.route("/archive")
def archive():
    """List every available daily dashboard, newest first."""
    dates = _daily_dates()
    if not dates:
        rows = '<li class="muted">No dashboards yet.</li>'
    else:
        items = []
        for i, d in enumerate(dates):
            tag = ' <span class="tag">Latest</span>' if i == 0 else ''
            items.append(f'<li><a href="/daily/{d}">{d}</a>{tag}</li>')
        rows = "\n".join(items)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Purands AI - Daily Archive</title>
<style>
  body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    background:#0f1115;color:#e8eaed;line-height:1.55}}
  main{{max-width:640px;margin:0 auto;padding:44px 20px}}
  h1{{font-size:20px;margin:0 0 4px}} .sub{{color:#9aa0aa;font-size:13px;margin-bottom:22px}}
  ul{{list-style:none;margin:0;padding:0}}
  li{{padding:11px 14px;border:1px solid #262a33;border-radius:8px;margin:8px 0;background:#181b22}}
  li a{{color:#7C5CFC;text-decoration:none;font-size:15px;font-weight:600}}
  .tag{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;
    background:rgba(124,92,252,.15);color:#7C5CFC;padding:2px 8px;border-radius:999px;margin-left:8px}}
  .muted{{color:#9aa0aa}} .back{{color:#7C5CFC;text-decoration:none;font-size:13px}}
</style></head><body><main>
  <h1>Daily Content Archive</h1>
  <div class="sub">{len(dates)} dashboard{"s" if len(dates) != 1 else ""} · newest first · nothing is auto-published</div>
  <p><a class="back" href="/">&larr; Comment Studio</a></p>
  <ul>
{rows}
  </ul>
</main></body></html>"""


@app.route("/assets/<path:subpath>")
def daily_assets(subpath: str):
    """Serve the daily dashboards' generated images (referenced as assets/... in
    the dashboard HTML) so they render on the hosted pages."""
    assets_root = _DAILY_DIR / "assets"
    return send_from_directory(str(assets_root), subpath)


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
