"""Timeline event render accounting tests (ADR-050 P1-A)."""

from __future__ import annotations

from narrare.consistency.timeline_fetch import _format_timeline_events
from narrare_core.context.contracts import RenderedKBContext


class FakeTimelineEvent:
    """Minimal event shape used by timeline_fetch."""

    def __init__(self) -> None:
        self.event_name = "Arrival"
        self.timestamp_raw = "Day 1"
        self.character_refs: list[dict[str, object]] | None = [{"id": "char-1", "name": "Alice"}]
        self.location_ref: dict[str, object] | None = {"id": "loc-1", "name": "Castle"}


def test_format_timeline_events_preserves_legacy_dicts_and_accounts_metadata() -> None:
    formatted, rendered = _format_timeline_events([FakeTimelineEvent()])

    assert formatted == [
        {
            "event_name": "Arrival",
            "timestamp": "Day 1",
            "character": "Alice",
            "location": "Castle",
        }
    ]
    assert isinstance(rendered, RenderedKBContext)
    assert rendered.entry_count == 1
    assert ("provenance", "consumer_cannot_act") in rendered.omitted_fields
