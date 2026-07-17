"""Shared value-container factories for ``confirm_extracted_event`` tests.

Holds the ``MagicMock(spec=...)`` novel / event factories used by the
extraction-confirm test modules (``test_extraction_confirm.py`` and the §7
follow-up ``test_extraction_confirm_kb_refs.py``). Extracted to comply with
RULE-04 (test-file size limit): both modules build the same lightweight
value-containers, so the factories live here once (ADR-030 — value-containers
with no domain behaviour are the legitimate ``MagicMock(spec=...)`` use).

Named ``_extraction_confirm_helpers`` to match the directory's
``_*_helpers`` / ``_*_fakes`` convention (e.g. ``_timeline_test_helpers``,
``_kb_context_helpers``).
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

#: Attribute surface exposed on the novel value-container.
_NOVEL_SPEC: tuple[str, ...] = ("id", "title", "genre", "writing_language")

#: Attribute surface exposed on the event value-container.
_EVENT_SPEC: tuple[str, ...] = (
    "id",
    "novel_id",
    "event_name",
    "description",
    "event_type",
    "timestamp_raw",
    "timestamp_normalized",
    "temporal_order",
    "chapter_id",
    "character_refs",
    "location_ref",
    "causes",
    "consequences",
    "source",
    "confidence",
    "is_confirmed",
    "created_at",
    "updated_at",
)


def make_novel(**overrides: object) -> MagicMock:
    """Create a mock novel value-container."""
    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Test Novel"),
        "genre": overrides.get("genre", "fantasy"),
        "writing_language": overrides.get("writing_language", "en"),
    }
    defaults.update(overrides)
    novel = MagicMock(spec=list(_NOVEL_SPEC))
    for k, v in defaults.items():
        setattr(novel, k, v)
    return novel


def make_event(**overrides: object) -> MagicMock:
    """Create a mock TimelineEvent value-container."""
    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "novel_id": overrides.get("novel_id", uuid.uuid4()),
        "event_name": overrides.get("event_name", "Battle"),
        "description": overrides.get("description", ""),
        "event_type": overrides.get("event_type", "plot_point"),
        "timestamp_raw": overrides.get("timestamp_raw", "Day 1"),
        "timestamp_normalized": overrides.get("timestamp_normalized", ""),
        "temporal_order": overrides.get("temporal_order", 1),
        "chapter_id": overrides.get("chapter_id"),
        "character_refs": overrides.get("character_refs", []),
        "location_ref": overrides.get("location_ref"),
        "causes": overrides.get("causes", ""),
        "consequences": overrides.get("consequences", ""),
        "source": overrides.get("source", "manual"),
        "confidence": overrides.get("confidence"),
        "is_confirmed": overrides.get("is_confirmed", True),
        "created_at": overrides.get("created_at", "2025-01-01T00:00:00Z"),
        "updated_at": overrides.get("updated_at", "2025-01-01T00:00:00Z"),
    }
    defaults.update(overrides)
    event = MagicMock(spec=list(_EVENT_SPEC))
    for k, v in defaults.items():
        setattr(event, k, v)
    return event
