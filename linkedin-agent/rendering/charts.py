"""Zero-dependency SVG chart renderer.

The Visual Designer produces a compact chart *spec* (labels + numeric values);
this module turns that spec into an inline SVG string the dashboard embeds
directly. No matplotlib, no external assets — the dashboard stays self-contained
and portable (it renders in any browser and survives being committed to GitHub).

Colours match the dashboard's dark theme. A chart is intentionally simple (a
single bar or line series) because that is what actually helps a LinkedIn reader
grasp one number or trend at a glance; anything richer is better as an image.
"""

from __future__ import annotations

from html import escape
from typing import Any

# Purands brand palette (see data/brand_visual.md) on the dashboard's dark panel.
_BG = "#1E1836"       # deep indigo base (brand dark panel)
_LINE = "#3a3357"     # subtle lilac-grey gridlines
_INK = "#f3f0fb"      # near-white ink
_MUTED = "#b9a5f7"    # lilac for axis/labels
_ACCENT = "#7C5CFC"   # vivid violet (bars, primary series)
_HIGH = "#B9A5F7"     # lilac (line series)

_W, _H = 720, 340
_PAD_L, _PAD_R, _PAD_T, _PAD_B = 56, 24, 44, 64


def render_chart(spec: dict[str, Any] | None) -> str:
    """Render a chart spec to an SVG string. Returns '' if the spec is unusable."""
    if not spec:
        return ""
    labels = [str(x) for x in (spec.get("labels") or [])]
    values = _coerce_numbers(spec.get("values") or [])
    # Pair up defensively — drop trailing items with no matching label/value.
    n = min(len(labels), len(values))
    if n == 0:
        return ""
    labels, values = labels[:n], values[:n]
    chart_type = str(spec.get("chart_type", "bar")).lower()
    title = str(spec.get("title", ""))
    x_label = str(spec.get("x_label", ""))
    y_label = str(spec.get("y_label", ""))
    source = str(spec.get("source", ""))

    if chart_type == "line":
        body = _line_body(labels, values)
    else:
        body = _bar_body(labels, values)

    parts: list[str] = [
        f'<svg viewBox="0 0 {_W} {_H}" width="100%" role="img" '
        f'xmlns="http://www.w3.org/2000/svg" style="max-width:{_W}px;font-family:'
        '-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">',
        f'<rect x="0" y="0" width="{_W}" height="{_H}" rx="8" fill="{_BG}" stroke="{_LINE}"/>',
    ]
    if title:
        parts.append(
            f'<text x="{_W/2:.0f}" y="26" text-anchor="middle" fill="{_INK}" '
            f'font-size="15" font-weight="700">{escape(title)}</text>'
        )
    parts.append(body)
    if y_label:
        parts.append(
            f'<text x="16" y="{(_PAD_T+ _plot_h()/2):.0f}" fill="{_MUTED}" font-size="11" '
            f'transform="rotate(-90 16 {(_PAD_T+_plot_h()/2):.0f})" text-anchor="middle">'
            f'{escape(y_label)}</text>'
        )
    if x_label:
        parts.append(
            f'<text x="{_W/2:.0f}" y="{_H-8}" text-anchor="middle" fill="{_MUTED}" '
            f'font-size="11">{escape(x_label)}</text>'
        )
    if source:
        parts.append(
            f'<text x="{_W-_PAD_R}" y="{_H-8}" text-anchor="end" fill="{_MUTED}" '
            f'font-size="10">{escape(source)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _plot_h() -> float:
    return _H - _PAD_T - _PAD_B


def _plot_w() -> float:
    return _W - _PAD_L - _PAD_R


def _coerce_numbers(values: list[Any]) -> list[float]:
    out: list[float] = []
    for v in values:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            out.append(0.0)
    return out


def _nice_max(v: float) -> float:
    """Round an axis max up to a clean value so gridlines read well."""
    if v <= 0:
        return 1.0
    import math
    exp = math.floor(math.log10(v))
    base = 10 ** exp
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * base:
            return m * base
    return 10 * base


def _fmt(v: float) -> str:
    if v == int(v):
        return str(int(v))
    return f"{v:.1f}"


def _axes(vmax: float) -> list[str]:
    """Baseline + horizontal gridlines with value labels."""
    px_l, px_t = _PAD_L, _PAD_T
    ph, pw = _plot_h(), _plot_w()
    parts: list[str] = []
    ticks = 4
    for i in range(ticks + 1):
        val = vmax * i / ticks
        y = px_t + ph - (ph * i / ticks)
        parts.append(
            f'<line x1="{px_l}" y1="{y:.1f}" x2="{px_l+pw:.1f}" y2="{y:.1f}" '
            f'stroke="{_LINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{px_l-8}" y="{y+4:.1f}" text-anchor="end" fill="{_MUTED}" '
            f'font-size="10">{_fmt(val)}</text>'
        )
    return parts


def _x_labels(labels: list[str], step: float, x0: float) -> list[str]:
    y = _PAD_T + _plot_h() + 16
    parts: list[str] = []
    for i, lab in enumerate(labels):
        x = x0 + step * i
        text = lab if len(lab) <= 14 else lab[:13] + "…"
        parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" fill="{_MUTED}" '
            f'font-size="11">{escape(text)}</text>'
        )
    return parts


def _bar_body(labels: list[str], values: list[float]) -> str:
    vmax = _nice_max(max(values + [0]))
    ph, pw = _plot_h(), _plot_w()
    px_l, px_t = _PAD_L, _PAD_T
    n = len(values)
    slot = pw / n
    bw = slot * 0.6
    parts = _axes(vmax)
    for i, v in enumerate(values):
        h = 0 if vmax == 0 else ph * (v / vmax)
        x = px_l + slot * i + (slot - bw) / 2
        y = px_t + ph - h
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" '
            f'rx="3" fill="{_ACCENT}"/>'
        )
        parts.append(
            f'<text x="{x+bw/2:.1f}" y="{y-6:.1f}" text-anchor="middle" fill="{_INK}" '
            f'font-size="11" font-weight="600">{_fmt(v)}</text>'
        )
    parts += _x_labels(labels, slot, px_l + slot / 2)
    return "".join(parts)


def _line_body(labels: list[str], values: list[float]) -> str:
    vmax = _nice_max(max(values + [0]))
    ph, pw = _plot_h(), _plot_w()
    px_l, px_t = _PAD_L, _PAD_T
    n = len(values)
    step = pw / (n - 1) if n > 1 else pw
    parts = _axes(vmax)
    pts = []
    for i, v in enumerate(values):
        x = px_l + step * i
        y = px_t + ph - (0 if vmax == 0 else ph * (v / vmax))
        pts.append((x, y))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    parts.append(
        f'<polyline points="{poly}" fill="none" stroke="{_HIGH}" stroke-width="2.5" '
        'stroke-linejoin="round" stroke-linecap="round"/>'
    )
    for (x, y), v in zip(pts, values):
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{_HIGH}"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y-8:.1f}" text-anchor="middle" fill="{_INK}" '
            f'font-size="11" font-weight="600">{_fmt(v)}</text>'
        )
    parts += _x_labels(labels, step, px_l)
    return "".join(parts)
