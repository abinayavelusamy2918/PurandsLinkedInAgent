"""Agent — Visual Designer.

Runs after Founder Voice. For each drafted post it decides whether a visual
would lift engagement and, if so, which one:

  - "chart" : the post already contains concrete numbers, so a simple bar/line
              chart clarifies them. The chart *spec* is stored on the draft and
              rendered to inline SVG at dashboard time (rendering/charts.py).
  - "image" : a concept illustration fits. A ready-to-use image prompt is stored,
              and — when image generation is enabled (config `images:` block) —
              a real PNG is generated and saved next to the dashboard so the user
              can attach/download it directly.
  - "none"  : the post is strongest as text alone.

Selective by design: many strong posts stay text-only. Nothing is auto-posted;
the visual is a suggestion attached to the post in the review dashboard.
"""

from __future__ import annotations

import json

from core.config import PACKAGE_ROOT
from core.images import build_image_client
from core.models import AgentResult, RunContext
from core.text import strip_long_dashes
from .base import BaseAgent, register

_VALID = {"chart", "image", "none"}


@register("visual_designer")
class VisualDesigner(BaseAgent):
    def execute(self, ctx: RunContext) -> AgentResult:
        if not ctx.drafts:
            self.log.info("No drafts to design visuals for")
            return AgentResult(agent=self.name, ok=True, data=[])

        if self.dry_run(ctx):
            self._attach_samples(ctx)
            return AgentResult(agent=self.name, ok=True,
                               data=[d.visual for d in ctx.drafts])

        specs = self._design(ctx)

        img_client = build_image_client(ctx.config, mode=ctx.config.get("mode", "full"))
        out_daily = ctx.config.get("paths", {}).get("output_daily", "output/daily")
        assets_rel_dir = f"assets/{ctx.run_date}"
        assets_abs_dir = PACKAGE_ROOT / out_daily / assets_rel_dir

        n_chart = n_image = n_generated = 0
        for i, draft in enumerate(ctx.drafts, start=1):
            visual = specs.get(i, {"kind": "none"})
            kind = visual.get("kind", "none")
            if kind == "chart":
                n_chart += 1
            elif kind == "image":
                n_image += 1
                prompt = visual.get("image_prompt", "")
                if img_client and prompt:
                    rel = f"{assets_rel_dir}/post{i}.png"
                    if img_client.generate(prompt, assets_abs_dir / f"post{i}.png"):
                        visual["image_path"] = rel   # relative to the dashboard HTML
                        n_generated += 1
                    else:
                        self.log.info("Post %d: image not generated, prompt kept for manual use", i)
            draft.visual = visual

        self.log.info("Visuals: %d charts, %d images (%d generated), %d text-only",
                      n_chart, n_image, n_generated, len(ctx.drafts) - n_chart - n_image)
        return AgentResult(agent=self.name, ok=True, data=[d.visual for d in ctx.drafts])

    # ------------------------------------------------------------------ #
    def _design(self, ctx: RunContext) -> dict[int, dict]:
        """Return {post_index (1-based): visual spec}. Empty/failed => all 'none'."""
        posts = [
            {"index": i, "topic": d.topic, "body": d.body,
             "purands_tie": d.purands_tie}
            for i, d in enumerate(ctx.drafts, start=1)
        ]
        prompt = self.prompts.get("visual_designer")
        system, user = prompt.render(
            brand_voice=self.brand(ctx, "brand_voice"),
            run_date=ctx.run_date,
            posts=json.dumps(posts, ensure_ascii=False, indent=2),
        )
        try:
            data = self.llm.complete_json(system, user)
        except Exception as exc:  # noqa: BLE001 — visuals are optional; never crash the run
            self.log.warning("Visual design failed: %s — posting text-only", exc)
            return {}

        out: dict[int, dict] = {}
        for entry in (data or []):
            try:
                idx = int(entry.get("index"))
            except (TypeError, ValueError):
                continue
            out[idx] = self._clean(entry)
        return out

    def _clean(self, entry: dict) -> dict:
        """Normalise one LLM entry into a safe, serialisable visual spec."""
        kind = str(entry.get("kind", "none")).lower()
        if kind not in _VALID:
            kind = "none"
        visual: dict = {
            "kind": kind,
            "caption": strip_long_dashes(str(entry.get("caption", ""))),
            "alt_text": strip_long_dashes(str(entry.get("alt_text", ""))),
        }
        if kind == "chart":
            chart = entry.get("chart") or {}
            labels = [str(x) for x in (chart.get("labels") or [])]
            values = self._nums(chart.get("values") or [])
            n = min(len(labels), len(values))
            if n < 2:                      # not enough real data to chart honestly
                visual["kind"] = "none"
                return visual
            visual["chart"] = {
                "chart_type": "line" if str(chart.get("chart_type")).lower() == "line" else "bar",
                "title": strip_long_dashes(str(chart.get("title", ""))),
                "x_label": strip_long_dashes(str(chart.get("x_label", ""))),
                "y_label": strip_long_dashes(str(chart.get("y_label", ""))),
                "labels": labels[:n],
                "values": values[:n],
                "source": strip_long_dashes(str(chart.get("source", ""))),
            }
        elif kind == "image":
            prompt = strip_long_dashes(str(entry.get("image_prompt", "") or ""))
            if not prompt:
                visual["kind"] = "none"
                return visual
            visual["image_prompt"] = prompt
            visual["style"] = strip_long_dashes(str(entry.get("style", "")))
        return visual

    @staticmethod
    def _nums(values: list) -> list[float]:
        out: list[float] = []
        for v in values:
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                continue
        return out

    def _attach_samples(self, ctx: RunContext) -> None:
        """Dry-run: give the first post a chart and the second an image prompt so
        the dashboard layout can be exercised without an API key."""
        for i, draft in enumerate(ctx.drafts):
            if i == 0:
                draft.visual = {
                    "kind": "chart",
                    "caption": "[DRY-RUN] Sample chart from post numbers.",
                    "alt_text": "Bar chart of sample retention figures.",
                    "chart": {
                        "chart_type": "bar", "title": "Sample metric by channel",
                        "x_label": "", "y_label": "%",
                        "labels": ["WhatsApp", "Email", "SMS"],
                        "values": [42, 18, 11], "source": "dry-run sample",
                    },
                }
            elif i == 1:
                draft.visual = {
                    "kind": "image",
                    "caption": "[DRY-RUN] Sample concept illustration.",
                    "alt_text": "Minimal isometric illustration of a retention workflow.",
                    "image_prompt": "Clean minimal isometric business illustration of an "
                                    "AI retention workflow, soft blues, no text, no logos.",
                    "style": "isometric-flat",
                }
            else:
                draft.visual = {"kind": "none", "caption": "", "alt_text": ""}
