"""Timeline entity metadata schema with grouped fields.

Fields capture the essential attributes of a fictional timeline
or historical period as recommended by the bundled timeline template.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .base import KBEntryMetadata


class TimelinePeriod(BaseModel):
    """Time period and date information."""

    model_config = ConfigDict(extra="allow")

    start_date: str | None = None
    end_date: str | None = None
    duration: str | None = None
    era_name: str | None = None


class TimelineEvents(BaseModel):
    """Key events and figures in the timeline."""

    model_config = ConfigDict(extra="allow")

    major_events: list[str] | None = None
    key_figures: list[str] | None = None
    conflicts: list[str] | None = None
    discoveries: list[str] | None = None


class TimelineMetadata(KBEntryMetadata):
    """Metadata for timeline KB entries with grouped fields.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    # Flat fields kept for backward compat
    era: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    first_appearance: str | None = None
    # Nested groups
    period: TimelinePeriod | None = None
    events: TimelineEvents | None = None
