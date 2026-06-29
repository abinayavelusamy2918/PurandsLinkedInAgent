"""Contract tests: every pipeline agent is registered and the full pipeline runs
end-to-end in dry-run mode (no API key, no network)."""

import agents  # noqa: F401  (registers agents)
import sources  # noqa: F401
from agents.base import registered_agents
from core.config import load_settings
from core.orchestrator import Orchestrator


def test_pipeline_agents_registered():
    settings = load_settings()
    reg = set(registered_agents())
    for name in settings.pipeline:
        assert name in reg, f"{name} not registered"


def test_full_pipeline_dry_run(tmp_path, monkeypatch):
    settings = load_settings()
    settings.mode = "dry-run"
    orch = Orchestrator(settings)
    ctx = orch.build_context(run_date="2026-01-01")
    orch.run(ctx)

    # Every agent should have produced a result and none should have errored.
    agent_names = {r.agent for r in ctx.results}
    for name in settings.pipeline:
        assert name in agent_names
    assert all(r.ok for r in ctx.results), [r.error for r in ctx.results if not r.ok]

    # Dry-run produces sample trends, research, and a draft.
    assert ctx.trends and ctx.researched and ctx.drafts


def test_dashboard_html_written(tmp_path):
    settings = load_settings()
    settings.mode = "dry-run"
    orch = Orchestrator(settings)
    ctx = orch.build_context(run_date="2026-01-02")
    orch.run(ctx)
    out = settings.path("output_daily") / "2026-01-02.html"
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "Daily Content Review" in html
    assert "Publishing Recommendation" in html
