"""Agent package.

Importing this package registers all built-in agents via their @register
decorators, so the orchestrator can look them up by name. To add an agent:
create a module here, subclass BaseAgent, decorate with @register("name"),
and import it below.
"""

from . import (  # noqa: F401  (imported for side-effect: registration)
    trend_hunter,
    research_analyst,
    founder_voice,
    visual_designer,
    engagement_agent,
    editor_publisher,
    comment_reply,
)
