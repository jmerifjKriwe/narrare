"""Core Pydantic schemas for Series, SeriesSettings, and Series read-models.

Pure value types (no HTTP/DB imports) owned by Core so Backend, MCP, A2A, and
CLI can share them (RULE-05/07/12).
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — needed at runtime for Pydantic model resolution
from typing import Literal
from uuid import UUID  # noqa: TC003 — needed at runtime for Pydantic model resolution

from pydantic import BaseModel, ConfigDict

SeriesStatus = Literal["draft", "active", "completed"]


class Series(BaseModel):
    """A series/reihe — groups multiple novels with shared Canon KB."""

    model_config = ConfigDict(extra="allow")

    id: UUID
    user_id: UUID
    title: str
    subtitle: str | None = None
    description: str | None = None
    genre: str | None = None
    writing_language: str | None = None
    status: SeriesStatus = "draft"
    planned_novel_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SeriesSettings(BaseModel):
    """1:1 settings for a Series. author_voice empty in Spec 1 (Spec 3 fills)."""

    model_config = ConfigDict(extra="allow")

    series_id: UUID
    author_voice: dict[str, object] | None = None
    context_window_size: int = 3  # Spec 2 recency-window default
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# NovelRow — Core read-model for "novels in a series" (RULE-09 typed return)
# ---------------------------------------------------------------------------


class NovelRow(BaseModel):
    """Core read-model of a Novel as returned by a series-novel listing.

    The concrete ``SeriesRepositoryProtocol.list_novels`` return type (RULE-09:
    a typed Core value object, not ``list[Any]`` — I-A2 fix). The apps-layer
    ``NovelSummaryResponse`` is built FROM this Core value object (the Response
    depends on Core, never the reverse — RULE-07 dependency direction). The
    concrete repository maps ORM ``Novel`` rows into ``NovelRow`` (analogous to
    how ``KBScopeRepository`` maps ORM rows into ``SeriesKBEntry``/``NovelKBEntry``).

    Optional timestamp/scalar fields default sensibly so Core stays pure and
    defensive; the repository populates them from always-set DB columns.
    """

    model_config = ConfigDict(extra="allow", from_attributes=True)

    id: UUID
    user_id: UUID
    series_id: UUID | None = None
    series_position: int | None = None
    title: str
    subtitle: str | None = None
    author: str = ""
    genre: str = ""
    writing_language: str = "en"
    is_demo: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# JoinReasonCode — machine-stable reason codes for Policy-alpha treatments (C3 fix)
# ---------------------------------------------------------------------------

JoinReasonCode = Literal[
    "entity_default_canon",
    "entity_default_overlay",
    "canon_nonempty_overlay",
]
"""Machine-stable reason codes for one Policy-alpha join treatment (C3 fix).

The backend's :class:`~narrare.series.schemas.JoinEntryTreatment` carries a
``reason_code`` the frontend resolves via i18n
(``series.join.reason.<code>``); the English ``reason`` tooltip on the same
schema is the human fallback for non-i18n clients (MCP/CLI — RULE-12 four-client
model). These Literal values are **stable wire values**: do NOT rename without a
coordinated migration of the i18n keys, or the frontend translation breaks
silently (the exact C3 failure this type exists to prevent).

Coverage of the Policy-alpha decision tree (``join_service._treatment_for``):
- ``entity_default_canon``    — canon empty + canon-preferring entity type
  (``system/concept/setting/location/object/timeline``) → promoted to Canon.
- ``entity_default_overlay``  — canon empty + overlay-preferring entity type
  (``character/faction``) → kept as Novel-Overlay.
- ``canon_nonempty_overlay``  — series Canon non-empty → entry stays Novel-Overlay.
"""
