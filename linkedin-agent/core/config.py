"""Configuration loading and validation.

Reads `config/config.yaml` and `config/sources.yaml`. Resolves paths relative
to the linkedin-agent package root so the app works the same locally and in CI.
Fails fast with a clear `ConfigError` if something required is missing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError

# linkedin-agent/  (parent of core/)
PACKAGE_ROOT = Path(__file__).resolve().parent.parent

# Where a dry-run writes instead of the real output. Keeps mock/placeholder
# content out of the recorded + hosted output/ and data/runs/ so a dry-run can
# never clobber a real dashboard. These dirs are gitignored.
_DRYRUN_SANDBOX = {
    "runs": "data/_dryrun/runs",
    "output_daily": "output/_dryrun/daily",
    "output_comments": "output/_dryrun/comments",
}


@dataclass
class LLMSettings:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 2000
    temperature: float = 0.7


@dataclass
class Settings:
    """Fully resolved runtime settings."""

    pipeline: list[str]
    llm: LLMSettings
    mode: str                                   # "full" | "dry-run"
    paths: dict[str, Path]
    sources: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict)

    def path(self, key: str) -> Path:
        try:
            return self.paths[key]
        except KeyError as exc:
            raise ConfigError(f"Unknown path key: {key!r}") from exc

    def apply_dryrun_sandbox(self) -> None:
        """Redirect every *write* path into the _dryrun sandbox.

        Idempotent. Updates both the resolved `paths` (used by the orchestrator)
        and `raw['paths']` (the relative strings agents read from ctx.config), so
        a dry-run's dashboards + run artifacts land in output/_dryrun and
        data/_dryrun and can never overwrite the real, recorded output.
        """
        raw_paths = self.raw.setdefault("paths", {})
        for key, rel in _DRYRUN_SANDBOX.items():
            self.paths[key] = (PACKAGE_ROOT / rel).resolve()
            raw_paths[key] = rel


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Config root must be a mapping: {path}")
    return data


def _resolve_paths(paths_cfg: dict[str, str]) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    for key, rel in paths_cfg.items():
        resolved[key] = (PACKAGE_ROOT / rel).resolve()
    return resolved


def load_settings(config_dir: Path | None = None) -> Settings:
    """Load and validate all configuration.

    Args:
        config_dir: Override the config directory (used by tests). Defaults to
            `<package_root>/config`.
    """
    cfg_dir = config_dir or (PACKAGE_ROOT / "config")
    config = _read_yaml(cfg_dir / "config.yaml")
    sources = _read_yaml(cfg_dir / "sources.yaml")

    pipeline = config.get("pipeline")
    if not isinstance(pipeline, list) or not pipeline:
        raise ConfigError("config.yaml: 'pipeline' must be a non-empty list of agent names")

    llm_cfg = config.get("llm", {})
    llm = LLMSettings(
        provider=llm_cfg.get("provider", "anthropic"),
        model=llm_cfg.get("model", "claude-sonnet-4-6"),
        max_tokens=int(llm_cfg.get("max_tokens", 2000)),
        temperature=float(llm_cfg.get("temperature", 0.7)),
    )

    mode = config.get("mode", "full")
    if mode not in {"full", "dry-run"}:
        raise ConfigError(f"config.yaml: 'mode' must be 'full' or 'dry-run', got {mode!r}")

    paths_cfg = config.get("paths") or {}
    # Sensible defaults so a minimal config still works.
    paths_cfg.setdefault("data", "data")
    paths_cfg.setdefault("runs", "data/runs")
    paths_cfg.setdefault("prompts", "templates/prompts")
    paths_cfg.setdefault("html_templates", "templates/html")
    paths_cfg.setdefault("output_daily", "output/daily")
    paths_cfg.setdefault("output_comments", "output/comments")
    paths = _resolve_paths(paths_cfg)

    settings = Settings(
        pipeline=pipeline,
        llm=llm,
        mode=mode,
        paths=paths,
        sources=sources,
        raw=config,
    )
    if mode == "dry-run":
        settings.apply_dryrun_sandbox()
    return settings


def require_env(name: str) -> str:
    """Fetch a required environment variable or raise ConfigError.

    Used for API keys so we never hardcode secrets and fail with a clear message
    in CI when a GitHub Secret is missing.
    """
    val = os.getenv(name)
    if not val:
        raise ConfigError(
            f"Required environment variable {name!r} is not set. "
            f"Set it locally in .env or as a GitHub Secret."
        )
    return val
