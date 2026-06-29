#!/usr/bin/env python3
"""Entry point for a daily run.

Run from anywhere:

    python linkedin-agent/scripts/run_daily.py
    # or, from inside linkedin-agent/:
    python scripts/run_daily.py [--date YYYY-MM-DD] [--dry-run]

Loads config, builds the orchestrator, runs the configured agent pipeline, and
writes the review dashboards + run artifacts. Reads ANTHROPIC_API_KEY (and any
optional source tokens) from the environment / .env.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the linkedin-agent package root importable regardless of CWD.
PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG_ROOT))

from core.config import load_settings              # noqa: E402
from core.logging_config import configure_logging, get_logger  # noqa: E402
from core.orchestrator import Orchestrator         # noqa: E402
import agents  # noqa: E402,F401  (registers all agents via side-effect)
import sources  # noqa: E402,F401  (registers all sources via side-effect)


def _load_dotenv() -> None:
    """Minimal .env loader (avoids an extra dependency). Ignores if absent."""
    env_file = PKG_ROOT.parent / ".env"
    if not env_file.exists():
        return
    import os
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Purands AI daily pipeline")
    parser.add_argument("--date", help="Run date (YYYY-MM-DD); defaults to today")
    parser.add_argument("--dry-run", action="store_true",
                        help="Force dry-run mode (mock LLM, no API key needed)")
    args = parser.parse_args(argv)

    _load_dotenv()
    configure_logging()
    log = get_logger("run_daily")

    settings = load_settings()
    if args.dry_run:
        settings.mode = "dry-run"

    log.info("Mode=%s | provider=%s | model=%s | pipeline=%s",
             settings.mode, settings.llm.provider, settings.llm.model,
             ", ".join(settings.pipeline))

    orch = Orchestrator(settings)
    ctx = orch.build_context(run_date=args.date)
    orch.run(ctx)

    failed = [r.agent for r in ctx.results if not r.ok]
    if failed:
        log.warning("Completed with failures in: %s", ", ".join(failed))
    else:
        log.info("Completed successfully. Dashboards in output/daily and output/comments.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
