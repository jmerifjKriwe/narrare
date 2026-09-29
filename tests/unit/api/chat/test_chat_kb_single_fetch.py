"""Unit tests for the chat KB single-fetch seam (#11 follow-up).

Before #11 the chat seam issued two provider calls per turn —
``fetch_context`` (slot types, filtered) plus ``fetch_entities`` (unfiltered)
to render the ``kb_other`` catch-all seam-side. The documented API sketch
merges this into ONE call: ``fetch_context`` fetches unfiltered once and
partitions slot types (renders + relationships) AND non-slot types into the
bundle's optional ``other`` render; the seam reads ``bundle.other`` instead
of performing the second fetch.

This module pins the two behaviors the merge must preserve:

* **single fetch** — the provider's ``fetch_context`` is called exactly once
  per turn and ``fetch_entities`` never (it stays reserved for raw-record
  consumers like timeline refs);
* **backward compatibility** — a pre-partition provider
  (``bundle.other is None``, e.g. filtered fetches or older implementations)
  degrades ``kb_other`` to ``""`` while the four slots resolve unchanged
  (the or-{} convention keeps baseline placeholders standing, RULE-11).

The ``kb_other`` count-cap pin (0baf3da9) moved with the render into the
provider suite (``tests/unit/api/kb/test_kb_context_provider.py``).

See:
    apps/api/narrare/kb/context_contracts.py (bundle.other contract),
    apps/api/narrare/chat/_context.py (resolve_chat_kb_vars seam),
    tests/unit/api/chat/_kb_context_fakes.py (partition-emulating double),
    CONSTRAINTS.md RULE-03/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from tests.unit.api.chat._kb_context_fakes import (
    KB_CHARACTERS,
    KB_FACTIONS,
    KB_LOCATIONS,
    KB_RELATIONSHIPS,
    OTHER_ENTITY_NAME,
    FakeKbContextProvider,
    other_entry,
    sentinel_bundle,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.context_contracts import KBContextBundle
    from narrare_core.context._render_options import RenderOptions


class _LegacyBundleProvider(FakeKbContextProvider):
    """Pre-partition provider double: ``fetch_context`` never sets ``other``."""

    async def fetch_context(
        self,
        novel_id: UUID,
        *,
        entity_types: list[str] | None = None,
        options: RenderOptions | None = None,
    ) -> KBContextBundle:
        self.fetch_context_calls.append(novel_id)
        if self._bundle is None:
            from narrare.kb.context_contracts import KBContextBundle

            return KBContextBundle.empty(options)
        return self._bundle


class TestSingleFetchPerTurn:
    """The seam fetches the provider exactly once per turn (#11)."""

    async def test_seam_fetches_context_once_and_never_entities(self) -> None:
        """One ``fetch_context`` call, zero ``fetch_entities`` calls."""
        from narrare.chat._context import resolve_chat_kb_vars

        novel_id = uuid4()
        provider = FakeKbContextProvider(
            bundle=sentinel_bundle(),
            entries=[other_entry()],
        )

        kb_vars = await resolve_chat_kb_vars(
            kb_context_provider=provider,
            novel_id=novel_id,
        )

        assert kb_vars is not None
        assert provider.fetch_context_calls == [novel_id]
        assert provider.fetch_entities_calls == []
        # kb_other flows from the bundle's partitioned ``other`` render.
        assert OTHER_ENTITY_NAME in kb_vars["kb_other"]


class TestBackwardCompatOtherAbsent:
    """Pre-partition providers (``other is None``) keep the old behavior."""

    async def test_bundle_without_other_degrades_kb_other_to_empty(self) -> None:
        """Slots resolve unchanged; ``kb_other`` degrades to ``""``."""
        from narrare.chat._context import resolve_chat_kb_vars

        kb_vars = await resolve_chat_kb_vars(
            kb_context_provider=_LegacyBundleProvider(bundle=sentinel_bundle()),
            novel_id=uuid4(),
        )

        assert kb_vars is not None
        assert kb_vars["kb_characters"] == KB_CHARACTERS
        assert kb_vars["kb_locations"] == KB_LOCATIONS
        assert kb_vars["kb_factions"] == KB_FACTIONS
        assert kb_vars["kb_relationships"] == KB_RELATIONSHIPS
        assert kb_vars["kb_other"] == ""
