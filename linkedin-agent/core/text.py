"""Small text-cleanup helpers shared across agents."""

from __future__ import annotations

import re


def strip_long_dashes(text: str) -> str:
    """Remove em/en dashes ("—", "–") from generated copy.

    Users asked that posts and comments never contain long dashes. A dash used as
    a sentence break (" — ") becomes a comma; any other long dash becomes a short
    hyphen. Leftover double spaces/commas are tidied.
    """
    if not text:
        return text
    # Dash used as a break with surrounding spaces -> comma.
    text = re.sub(r"\s+[—–]\s+", ", ", text)
    # Any remaining long dash (e.g. joined to words) -> short hyphen.
    text = text.replace("—", "-").replace("–", "-")
    # Tidy artefacts.
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    return text.strip()


def strip_trailing_question(text: str) -> str:
    """Guarantee text never ends open-ended. If the final sentence is a question,
    drop it; if what remains still ends with '?', trim it."""
    if not text:
        return text
    parts = re.findall(r"[^.!?]*[.!?]|[^.!?]+$", text)
    parts = [p for p in (p.strip() for p in parts) if p]
    while parts and parts[-1].endswith("?"):
        parts.pop()
    cleaned = " ".join(parts).strip() if parts else text.rstrip(" ?")
    return cleaned or text.rstrip(" ?")
