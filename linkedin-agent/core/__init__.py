"""Core infrastructure for the Purands AI platform.

This package holds cross-cutting concerns that every agent and source relies on:
configuration, the LLM client, the prompt loader, shared data models, logging,
the orchestrator, and custom errors. Nothing here knows about LinkedIn
specifically — it is the reusable spine for future products/agents.
"""
