"""Shared helpers for KBRepository scope-query unit tests.

Extracted to keep the test files under the RULE-04 400-line limit. Provides
builders for mock SQLAlchemy Results and real (unpersisted) ``KBEntry`` ORM
instances — real instances are required because the scope converters construct
Core Pydantic types from model attributes.

These functions are the module's public test API (no leading underscore) so
that cross-module imports don't trip pyright's ``reportPrivateUsage``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from narrare.kb.models import KBEntry
from narrare.novels.models import Novel

if TYPE_CHECKING:
    from collections.abc import Sequence

_RESULT_ATTRS = ["scalars", "scalar_one_or_none", "scalar_one"]


def _returning(value: object) -> MagicMock:
    """Callable mock returning *value* — satisfies RULE-TEST-01."""
    return MagicMock(spec=[], return_value=value)


def make_result(
    *,
    scalars: Sequence[object] | None = None,
    scalar_one_or_none: object = None,
) -> MagicMock:
    """Create a MagicMock mimicking SQLAlchemy's Result.

    The Result returned by ``session.execute()`` has synchronous methods
    (``.scalars()``, ``.scalar_one_or_none()``), so we use ``MagicMock``.
    """
    result: MagicMock = MagicMock(spec=_RESULT_ATTRS)
    if scalars is not None:
        # result.scalars() -> the sequence itself (iterable), matching repo style.
        result.scalars = _returning(scalars)
    result.scalar_one_or_none = _returning(scalar_one_or_none)
    return result


def make_kb_model(**overrides: object) -> KBEntry:
    """Create a real (unpersisted) KBEntry ORM instance with sane defaults.

    Real instances are required because the scope converters construct Core
    Pydantic objects from model attributes — MagicMock attributes would fail
    Pydantic validation and would not exercise the converter truthfully.
    """
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "novel_id": uuid.uuid4(),
        "series_id": None,
        "base_entry_id": None,
        "entity_type": "character",
        "name": "Test Entry",
        "slug": "test-entry",
        "status": "draft",
        "body": "Some body text",
        "metadata_": {"key": "value"},
        "tags": ["tag1", "tag2"],
        "template_version": "1.0",
        "source": "manual",
        "review_status": "approved",
        "embeddings_dirty": False,
        "last_referenced_at": None,
        "usage_count": 0,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return KBEntry(**defaults)


def make_novel(**overrides: object) -> MagicMock:
    """Create a mock Novel (only id/series_id are read by the repository)."""
    novel: MagicMock = MagicMock(spec=Novel)
    novel.id = overrides.get("id", uuid.uuid4())
    novel.series_id = overrides.get("series_id", uuid.uuid4())
    return novel
