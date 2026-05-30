"""Shared data types for the change engine subsystem.

Extracted from ``change_engine.py`` to avoid circular imports between
:mod:`change_engine` and :mod:`_change_classify`.

These are pure data containers — no I/O, no side-effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True, slots=True)
class DiffOp:
    """A single diff operation between original and revised text.

    Maps directly to a :func:`~difflib.SequenceMatcher.get_opcodes` entry.
    Operation types follow ``difflib`` conventions:

    * ``"equal"`` — text unchanged (filtered out in public results)
    * ``"insert"`` — text added in revised version
    * ``"delete"`` — text removed from original
    * ``"replace"`` — text changed
    """

    type: Literal["equal", "insert", "delete", "replace"]
    original_start: int  # character offset in original
    original_end: int
    revised_start: int  # character offset in revised
    revised_end: int
    content_original: str  # text in original (empty for insert)
    content_revised: str  # text in revised (empty for delete)


@dataclass(frozen=True, slots=True)
class ChangeGroup:
    """A grouped set of related changes (typically one sentence).

    Groups multiple adjacent :class:`DiffOp` instances that fall within
    the same sentence boundary in the original text.
    """

    original_text: str
    revised_text: str
    ops: list[DiffOp] = field(default_factory=lambda: [])
    change_type: str = "word_choice"
    index: int = 0


@dataclass(frozen=True, slots=True)
class DiffResult:
    """Complete diff result with metadata.

    The primary return type for :func:`~change_engine.compute_changes`.
    """

    original: str
    revised: str
    changes: list[ChangeGroup] = field(default_factory=lambda: [])
    total_changes: int = 0
    has_changes: bool = False
