#!/usr/bin/env python3
"""Build a static site from the generated review dashboards for GitHub Pages.

Copies every daily dashboard (and its image assets) into an output directory and
writes an index page that lists them newest-first, linking the most recent as
"Latest". Run by the Pages workflow; also runnable locally:

    python3 linkedin-agent/scripts/build_site.py _site
"""

from __future__ import annotations

import re
import shutil
import sys
from html import escape
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = PKG_ROOT / "output" / "daily"
ASSETS_DIR = DAILY_DIR / "assets"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _dashboards() -> list[str]:
    """Return dashboard dates (YYYY-MM-DD) newest-first."""
    dates = [p.stem for p in DAILY_DIR.glob("*.html") if _DATE_RE.match(p.stem)]
    return sorted(dates, reverse=True)


def build(out_dir: Path) -> None:
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "daily").mkdir(parents=True, exist_ok=True)

    dates = _dashboards()
    # Copy each dashboard + shared assets so relative asset links resolve.
    for d in dates:
        shutil.copy2(DAILY_DIR / f"{d}.html", out_dir / "daily" / f"{d}.html")
    if ASSETS_DIR.exists():
        shutil.copytree(ASSETS_DIR, out_dir / "daily" / "assets", dirs_exist_ok=True)

    (out_dir / ".nojekyll").write_text("")   # serve _-prefixed asset dirs verbatim
    (out_dir / "index.html").write_text(_index_html(dates), encoding="utf-8")
    print(f"Built site with {len(dates)} dashboard(s) -> {out_dir}")


def _index_html(dates: list[str]) -> str:
    rows = []
    for i, d in enumerate(dates):
        latest = ' <span class="tag">Latest</span>' if i == 0 else ""
        rows.append(
            f'<li><a href="daily/{escape(d)}.html">{escape(d)}</a>{latest}</li>'
        )
    items = "\n".join(rows) or '<li class="muted">No dashboards generated yet.</li>'
    latest_link = (
        f'<a class="cta" href="daily/{escape(dates[0])}.html">Open latest dashboard &rarr;</a>'
        if dates else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Purands AI - Daily Content Review</title>
<style>
  :root{{--bg:#0f1115;--card:#181b22;--ink:#e8eaed;--muted:#9aa0aa;--line:#262a33;--accent:#7C5CFC}}
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    background:var(--bg);color:var(--ink);line-height:1.55}}
  main{{max-width:720px;margin:0 auto;padding:48px 20px}}
  h1{{font-size:22px;margin:0 0 6px}}
  .sub{{color:var(--muted);font-size:14px;margin-bottom:24px}}
  .cta{{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;
    padding:10px 18px;border-radius:8px;font-size:14px;font-weight:600;margin-bottom:28px}}
  ul{{list-style:none;margin:0;padding:0}}
  li{{padding:12px 14px;border:1px solid var(--line);border-radius:8px;margin:8px 0;background:var(--card)}}
  li a{{color:var(--accent);text-decoration:none;font-size:15px;font-weight:600}}
  .tag{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;
    background:rgba(124,92,252,.15);color:var(--accent);padding:2px 8px;border-radius:999px;margin-left:8px}}
  .muted{{color:var(--muted)}}
  footer{{color:var(--muted);font-size:12px;margin-top:28px}}
</style>
</head>
<body>
<main>
  <h1>Purands AI - Daily Content Review</h1>
  <div class="sub">Generated LinkedIn posts, comments &amp; visuals for review. Nothing is auto-published.</div>
  {latest_link}
  <h2 style="font-size:15px;color:var(--muted)">All dashboards</h2>
  <ul>
{items}
  </ul>
  <footer>Regenerated automatically on each pipeline run.</footer>
</main>
</body>
</html>"""


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else PKG_ROOT.parent / "_site"
    build(target)
