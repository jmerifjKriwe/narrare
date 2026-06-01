"""Dependency types for InlineSuggestAgent.

Minimal context for low-latency inline text completions.
Only essential KB data (characters) — no locations, factions, or chapter outline.
Keep it fast (<500ms target).

See WRITE-007 (Inline AI Suggestions / Ghost Text).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class InlineSuggestDeps:
    """Dependencies for inline text suggestions.

    Attributes:
        text_before: Last ~200 tokens of text before cursor (required).
        text_after: Text after cursor, if any (e.g. for mid-sentence insertions).
        chapter_context: Brief chapter context — POV, setting, time.
        user_preferences: Style preferences from memory layer.
        kb_characters: KB character data for name accuracy and dialogue voice.
    """

    text_before: str
    text_after: str | None = None
    chapter_context: str | None = None
    user_preferences: str | None = None
    kb_characters: str | None = None  # KB character data for name accuracy
