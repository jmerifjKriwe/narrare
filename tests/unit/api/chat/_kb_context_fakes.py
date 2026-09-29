"""Shared test doubles for the ChatService KB-context wiring tests (ADR-067).

Holds the fake ``KBContextProviderProtocol`` implementation, the per-slot
sentinels, and the ``KBEntry`` factories used by
``test_chat_service_kb_context.py``. Extracted to respect the 400-line test
file-size limit (RULE-04).

Named ``_kb_context_fakes`` to match the directory's ``_*_fakes`` /
``_*_helpers`` convention (e.g. ``tests/unit/api/kb/_kb_context_helpers.py``).
Symbols are public (no leading underscore) because they are imported by the
sibling test module.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import uuid4

from narrare.kb._context_provider import kb_entry_to_kb_entity
from narrare.kb.context_contracts import KBContextBundle
from narrare.kb.models import KBEntry
from narrare_core.context._kb_envelope import RenderedKBContext
from narrare_core.context._render_options import RenderOptions
from narrare_core.writing._helpers import format_entities

if TYPE_CHECKING:
    from uuid import UUID

#: Slot types the bundle carries — every other entity type partitions into
#: ``other`` (mirrors the real provider's single-fetch partition, #11).
_SLOT_TYPES: frozenset[str] = frozenset({"character", "location", "faction"})

# ---------------------------------------------------------------------------
# Sentinels — one per bundle slot; kb_other flows through the real renderer,
# so its assertion key is the seeded entity name instead of a literal.
# ---------------------------------------------------------------------------
KB_CHARACTERS = "SENTINEL_KB_CHARACTERS_3a91"
KB_LOCATIONS = "SENTINEL_KB_LOCATIONS_5b22"
KB_FACTIONS = "SENTINEL_KB_FACTIONS_7c43"
KB_RELATIONSHIPS = "SENTINEL_KB_RELATIONSHIPS_9d64"

OTHER_ENTITY_NAME = "The Weave"
OTHER_ENTITY_BODY = "Magic underlying the world."

#: Full kb_vars key set (4 bundle slots + the chat-side kb_other catch-all).
CHAT_KB_VARS_KEYS = frozenset(
    {"kb_characters", "kb_locations", "kb_factions", "kb_relationships", "kb_other"}
)


def rendered(text: str) -> RenderedKBContext:
    """Bundle-slot stand-in (provenance accounting not asserted here)."""
    return RenderedKBContext(
        text=text,
        preserved_fields=frozenset(),
        omitted_fields=(),
        entry_count=1,
        render_path="test.rendered",
    )


def sentinel_bundle() -> KBContextBundle:
    """A populated bundle: one sentinel per ADR-067 slot."""
    return KBContextBundle(
        characters=rendered(KB_CHARACTERS),
        locations=rendered(KB_LOCATIONS),
        factions=rendered(KB_FACTIONS),
        relationships=rendered(KB_RELATIONSHIPS),
        render_options=RenderOptions(annotate_provenance=True),
    )


def entry(entity_type: str, name: str, body: str = "") -> KBEntry:
    """A real ``KBEntry`` (defaults unused by the seam are server-side)."""
    return KBEntry(
        novel_id=uuid4(),
        entity_type=entity_type,
        name=name,
        slug=name.lower().replace(" ", "-"),
        body=body,
    )


def other_entry() -> KBEntry:
    """A non-slot-type entry that must land in the ``kb_other`` catch-all."""
    return entry("system", OTHER_ENTITY_NAME, OTHER_ENTITY_BODY)


class FakeKbContextProvider:
    """Fake ``KBContextProviderProtocol`` — configured bundle + raw entries.

    Records ``fetch_context`` / ``fetch_entities`` calls so tests can pin
    that project-less chat performs no KB fetches (NOTES-001 §6b).
    """

    def __init__(
        self,
        *,
        bundle: KBContextBundle | None = None,
        entries: list[KBEntry] | None = None,
    ) -> None:
        self._bundle = bundle
        self._entries = entries or []
        self.fetch_context_calls: list[UUID] = []
        self.fetch_entities_calls: list[UUID] = []

    async def fetch_context(
        self,
        novel_id: UUID,
        *,
        entity_types: list[str] | None = None,
        options: RenderOptions | None = None,
    ) -> KBContextBundle:
        self.fetch_context_calls.append(novel_id)
        bundle = self._bundle if self._bundle is not None else KBContextBundle.empty(options)
        if entity_types is not None:
            # Caller-scoped fetch: the caller owns the type scope, ``other``
            # stays ``None`` (real-provider contract, backward compatible).
            return bundle
        # Single-fetch partition (#11): non-slot entries render into
        # ``bundle.other`` through the real capped formatter — exactly like
        # the production provider.
        other_entities = [
            kb_entry_to_kb_entity(kb_entry)
            for kb_entry in self._entries
            if kb_entry.entity_type not in _SLOT_TYPES
        ]
        return replace(bundle, other=format_entities(other_entities, options=options))

    async def fetch_entities(
        self,
        novel_id: UUID,
        *,
        entity_types: list[str] | None = None,
    ) -> list[KBEntry]:
        self.fetch_entities_calls.append(novel_id)
        return list(self._entries)

    async def fetch_world_context(
        self,
        novel_id: UUID,
        *,
        entity_type: str | None = None,
        max_entries: int = 30,
    ) -> str:
        return ""
