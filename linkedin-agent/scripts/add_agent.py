#!/usr/bin/env python3
"""Scaffold a new agent so the platform is trivial to extend.

    python linkedin-agent/scripts/add_agent.py my_new_agent

Creates agents/my_new_agent.py and templates/prompts/my_new_agent.md from a
template, then prints the two follow-up steps (import + pipeline entry). It never
overwrites existing files.
"""

from __future__ import annotations

import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent

AGENT_TEMPLATE = '''"""Agent — {title}.

TODO: describe what this agent does and what it attaches to the RunContext.
"""

from __future__ import annotations

from core.models import AgentResult, RunContext
from .base import BaseAgent, register


@register("{name}")
class {cls}(BaseAgent):
    def execute(self, ctx: RunContext) -> AgentResult:
        if self.dry_run(ctx):
            return AgentResult(agent=self.name, ok=True, data={{"note": "dry-run"}})

        prompt = self.prompts.get("{name}")
        system, user = prompt.render(
            run_date=ctx.run_date,
            # add the variables your prompt needs here
        )
        result = self.llm.complete_json(system, user)
        # TODO: map `result` into models and attach to ctx
        return AgentResult(agent=self.name, ok=True, data=result)
'''

PROMPT_TEMPLATE = '''--- system ---
You are the {title} for Purands AI. Describe the role and the strict output
contract here. Return STRICT JSON only.

--- user ---
Today is {{run_date}}. Provide the inputs the agent needs.
'''


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: add_agent.py <snake_case_name>")
        return 2
    name = argv[0]
    cls = "".join(part.capitalize() for part in name.split("_"))
    title = name.replace("_", " ").title()

    agent_path = PKG_ROOT / "agents" / f"{name}.py"
    prompt_path = PKG_ROOT / "templates" / "prompts" / f"{name}.md"
    for p in (agent_path, prompt_path):
        if p.exists():
            print(f"refusing to overwrite existing file: {p}")
            return 1

    agent_path.write_text(
        AGENT_TEMPLATE.format(title=title, name=name, cls=cls), encoding="utf-8")
    prompt_path.write_text(
        PROMPT_TEMPLATE.format(title=title), encoding="utf-8")

    print(f"Created {agent_path}")
    print(f"Created {prompt_path}")
    print("\nNext steps:")
    print(f"  1. Add `    {name},` to the import list in agents/__init__.py")
    print(f"  2. Add `  - {name}` to the pipeline in config/config.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
