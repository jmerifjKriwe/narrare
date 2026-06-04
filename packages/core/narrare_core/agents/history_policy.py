"""History policy for Narrare agents (ADR-034).

Defines whether an agent receives process history across turns.
Task agents get no history; conversational agents opt in.
"""

from __future__ import annotations

from enum import Enum


class HistoryPolicy(Enum):
    """Determines whether an agent accumulates process history.

    - NONE: Task agent — no ProcessHistory. Each run is isolated.
      Default for all agents unless explicitly declared otherwise.
    - CONVERSATIONAL: Conversational agent — ProcessHistory enabled.
      Used for multi-turn conversations (Chat, Interactive Writing, Co-Author).
    """

    NONE = "none"
    CONVERSATIONAL = "conversational"
