"""Prompt loader behaviour."""

from pathlib import Path

import pytest

from core.config import PACKAGE_ROOT
from core.errors import PromptNotFoundError
from core.prompts import PromptLoader


def test_all_pipeline_prompts_exist_and_split():
    loader = PromptLoader(PACKAGE_ROOT / "templates" / "prompts")
    for key in ["trend_hunter", "research_analyst", "founder_voice",
                "engagement_agent", "editor_publisher", "comment_reply"]:
        prompt = loader.get(key)
        assert prompt.system_template, f"{key} has empty system prompt"


def test_missing_prompt_raises():
    loader = PromptLoader(PACKAGE_ROOT / "templates" / "prompts")
    with pytest.raises(PromptNotFoundError):
        loader.get("does_not_exist")


def test_safe_format_leaves_unknown_placeholder(tmp_path: Path):
    p = tmp_path / "x.md"
    p.write_text("--- system ---\nHello {known} and {unknown}\n--- user ---\nu", encoding="utf-8")
    loader = PromptLoader(tmp_path)
    system, _ = loader.get("x").render(known="world")
    assert "world" in system
    assert "{unknown}" in system  # missing var preserved, not crashed
