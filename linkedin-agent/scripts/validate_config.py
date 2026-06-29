#!/usr/bin/env python3
"""Pre-flight config validation. Run before a real pipeline run / in CI.

Checks that config + sources parse, every pipeline agent is registered, every
configured source is registered, and required prompt files exist.

    python linkedin-agent/scripts/validate_config.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG_ROOT))

from core.config import load_settings           # noqa: E402
from core.logging_config import configure_logging, get_logger  # noqa: E402
import agents  # noqa: E402,F401
import sources  # noqa: E402,F401
from agents.base import registered_agents       # noqa: E402
from sources.base import registered_sources     # noqa: E402


def main() -> int:
    configure_logging()
    log = get_logger("validate")
    problems: list[str] = []

    settings = load_settings()

    reg_agents = set(registered_agents())
    for name in settings.pipeline:
        if name not in reg_agents:
            problems.append(f"pipeline agent not registered: {name!r}")

    reg_sources = set(registered_sources())
    for entry in settings.sources.get("sources", []):
        if entry.get("enabled") and entry.get("name") not in reg_sources:
            problems.append(f"enabled source not registered: {entry.get('name')!r}")

    prompts_dir = settings.path("prompts")
    for name in settings.pipeline:
        if not (prompts_dir / f"{name}.md").exists():
            problems.append(f"missing prompt file: templates/prompts/{name}.md")

    if problems:
        for p in problems:
            log.error("VALIDATION: %s", p)
        log.error("Validation FAILED with %d problem(s)", len(problems))
        return 1
    log.info("Validation OK. Agents=%s Sources=%s",
             ", ".join(sorted(reg_agents)), ", ".join(sorted(reg_sources)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
