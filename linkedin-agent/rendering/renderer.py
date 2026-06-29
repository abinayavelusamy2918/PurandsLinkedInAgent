"""Jinja2-based HTML renderer.

Two entry points:
  - render_dashboard(ctx, editorial, out_dir) -> daily review dashboard
  - render_comments(ctx, out_dir)            -> comment-reply review page

Templates live in templates/html/ and are self-contained (inline CSS/JS), so the
output opens in any browser and survives being committed to GitHub.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import PACKAGE_ROOT
from core.logging_config import get_logger
from core.models import RunContext

log = get_logger(__name__)

_TEMPLATE_DIR = PACKAGE_ROOT / "templates" / "html"


def _env():
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Jinja2 not installed; `pip install Jinja2`") from exc
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    env.filters["confidence_class"] = _confidence_class
    return env


def _confidence_class(value: float) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "low"
    if v >= 0.75:
        return "high"
    if v >= 0.5:
        return "medium"
    return "low"


def render_dashboard(ctx: RunContext, editorial: dict[str, Any], out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    template = _env().get_template("dashboard.html.j2")
    html = template.render(
        run_date=ctx.run_date,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        trends=[t.to_dict() for t in ctx.trends],
        researched=[r.to_dict() for r in ctx.researched],
        drafts=[d.to_dict() for d in ctx.drafts],
        comments=[c.to_dict() for c in ctx.comments],
        editorial=editorial,
    )
    out_path = out_dir / f"{ctx.run_date}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def render_comments(ctx: RunContext, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    template = _env().get_template("comments.html.j2")
    html = template.render(
        run_date=ctx.run_date,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        replies=[r.to_dict() for r in ctx.replies],
    )
    out_path = out_dir / f"{ctx.run_date}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
