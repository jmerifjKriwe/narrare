"""Scratchpad notes — pure value types and normalization rules (NOTES-001).

Language-neutral note-type keys; display names come from the ``notes.type.*``
i18n namespace (en/de/fr). Pure module: no I/O, no frameworks, no DB.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class NoteLimits:
    """Domain limits for scratchpad notes.

    RULE-18: limits live in a Limits class, not loose module constants.
    """

    max_tags_per_note: int = 10
    max_tag_length: int = 32
    fallback_title_max_length: int = 200


#: Default limits per the spec (§4): max 10 tags x 32 chars per tag,
#: fallback title clipped to 200 chars.
DEFAULT_NOTE_LIMITS = NoteLimits()


class NoteType(StrEnum):
    """Language-neutral note type keys — displayed via i18n ``notes.type.*``."""

    IDEA = "idea"
    CONCEPT = "concept"
    QUESTION = "question"
    OTHER = "other"


class ScopeError(ValueError):
    """A note cannot link to both a novel and a series (spec §4 invariant)."""


def validate_scope(novel_id: UUID | None, series_id: UUID | None) -> None:
    """Enforce the scope invariant: at most ONE of novel/series link set.

    Both ``None`` (a global note) is the normal case and always valid.
    """
    if novel_id is not None and series_id is not None:
        raise ScopeError("A note can link to a novel or a series, not both.")


def normalize_tag(tag: str) -> str:
    """Normalize a single tag: trim, lowercase, collapse inner whitespace."""
    return _WHITESPACE_RE.sub(" ", tag.strip()).lower()


def normalize_tags(tags: list[str], *, limits: NoteLimits = DEFAULT_NOTE_LIMITS) -> list[str]:
    """Normalize a tag list.

    Per tag: :func:`normalize_tag` + clip to ``limits.max_tag_length``; empty
    results are dropped. Across tags: dedupe case-insensitively (first
    occurrence wins, order preserved) and cap the list at
    ``limits.max_tags_per_note``.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in tags:
        tag = normalize_tag(raw)[: limits.max_tag_length]
        if not tag or tag in seen:
            continue
        seen.add(tag)
        ordered.append(tag)
        if len(ordered) == limits.max_tags_per_note:
            break
    return ordered


def fallback_title(content: str, *, limits: NoteLimits = DEFAULT_NOTE_LIMITS) -> str:
    """First non-empty content line, clipped — the title when none is given."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[: limits.fallback_title_max_length]
    return ""


def effective_title(
    title: str | None,
    content: str,
    *,
    limits: NoteLimits = DEFAULT_NOTE_LIMITS,
) -> str:
    """The display title: the given (non-blank) title, or the content fallback."""
    if title is not None and title.strip():
        return title.strip()
    return fallback_title(content, limits=limits)
