"""Unit tests for the reusable KB-context provider — fetch/render behavior (ADR-067).

This module is the first half of the split KB-context provider test suite
(extracted to respect the 400-line test file-size limit, RULE-04). It covers
the fetch + render path:

* ``kb_entry_to_kb_entity`` — the canonical KBEntry→KBEntity mapper;
* populated KB → non-empty per-type renderings (characters/locations/factions
  + relationships);
* RULE-11 graceful degradation (``None`` repo / failing repo / empty KB →
  empty bundle, never an exception);
* ``fetch_world_context`` delegation.

Provenance accounting, ``to_prompt_variables()`` mapping, and Protocol
compliance live in ``test_kb_context_provider_provenance.py``. Shared test
doubles come from ``_kb_context_helpers``.

The provider's fetch path is the real :func:`list_entities` +
:func:`format_entities` + :func:`format_relationships`; only the repositories
are faked.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.kb._context_provider import kb_entry_to_kb_entity
from tests.unit.api.kb._kb_context_helpers import (
    Edge,
    FailingKBRepo,
    FailingRelRepo,
    FakeKBRepo,
    FakeRelRepo,
    make_entry,
    make_provider,
    populated_entries,
)

# ---------------------------------------------------------------------------
# kb_entry_to_kb_entity — the canonical KBEntry→KBEntity mapper
# ---------------------------------------------------------------------------


class TestKbEntryToKbEntity:
    def test_maps_core_and_provenance_fields(self) -> None:
        entry = make_entry(
            "Elara",
            "character",
            body="A storm-caller.",
            source="auto_extraction",
            review_status="pending",
            status="draft",
        )

        entity = kb_entry_to_kb_entity(entry)  # type: ignore[arg-type]

        assert entity.entity_type == "character"
        assert entity.name == "Elara"
        assert entity.content == "A storm-caller."
        # Provenance carried through so format_entities can render brackets.
        assert entity.source == "auto_extraction"
        assert entity.review_status == "pending"
        assert entity.status == "draft"

    def test_missing_body_yields_empty_content(self) -> None:
        entry = make_entry("Elara")
        entry.body = None  # simulate a KB entry with a null body

        entity = kb_entry_to_kb_entity(entry)  # type: ignore[arg-type]

        assert entity.content == ""


# ---------------------------------------------------------------------------
# fetch_context — populated KB
# ---------------------------------------------------------------------------


class TestFetchContextPopulated:
    @pytest.mark.asyncio
    async def test_renders_each_entity_slot_non_empty(self) -> None:
        provider = make_provider(FakeKBRepo(populated_entries()))

        bundle = await provider.fetch_context(uuid4())

        assert "Elara" in bundle.characters.text
        assert "Shimmering Keep" in bundle.locations.text
        assert "Night Watch" in bundle.factions.text
        # Entry counts flow through (ADR-050 accounting).
        assert bundle.characters.entry_count == 1
        assert bundle.locations.entry_count == 1
        assert bundle.factions.entry_count == 1

    @pytest.mark.asyncio
    async def test_renders_relationships_when_rel_repo_present(self) -> None:
        edges: list[Edge] = [("Elara", "ally_of", None, "Marcus", "directed")]
        provider = make_provider(FakeKBRepo([]), FakeRelRepo(edges))

        bundle = await provider.fetch_context(uuid4())

        assert "Elara" in bundle.relationships.text
        assert "Marcus" in bundle.relationships.text
        assert "→" in bundle.relationships.text
        assert bundle.relationships.entry_count == 1

    @pytest.mark.asyncio
    async def test_non_slot_entity_types_are_fetched_but_ignored(self) -> None:
        """A ``system`` entry is fetched but not routed to any bundle slot."""
        entries = [make_entry("The Calendar", "system"), make_entry("Elara", "character")]
        provider = make_provider(FakeKBRepo(entries))

        bundle = await provider.fetch_context(uuid4())

        assert bundle.characters.text != ""
        assert "Calendar" not in bundle.characters.text
        assert bundle.locations.text == ""
        assert bundle.factions.text == ""

    @pytest.mark.asyncio
    async def test_entity_types_filter_restricts_rendered_slots(self) -> None:
        provider = make_provider(FakeKBRepo(populated_entries()))

        bundle = await provider.fetch_context(uuid4(), entity_types=["character"])

        assert bundle.characters.text != ""
        # location/faction were filtered out at fetch time.
        assert bundle.locations.text == ""
        assert bundle.factions.text == ""


# ---------------------------------------------------------------------------
# fetch_context — RULE-11 graceful degradation
# ---------------------------------------------------------------------------


class TestFetchContextDegradation:
    @pytest.mark.asyncio
    async def test_none_kb_repo_yields_empty_bundle_without_raising(self) -> None:
        provider = make_provider(None)

        bundle = await provider.fetch_context(uuid4())

        assert bundle.characters.text == ""
        assert bundle.locations.text == ""
        assert bundle.factions.text == ""
        assert bundle.relationships.text == ""

    @pytest.mark.asyncio
    async def test_failing_kb_repo_yields_empty_bundle_without_raising(self) -> None:
        provider = make_provider(FailingKBRepo())

        bundle = await provider.fetch_context(uuid4())

        assert bundle.characters.text == ""
        assert bundle.locations.text == ""

    @pytest.mark.asyncio
    async def test_empty_kb_yields_empty_bundle_without_raising(self) -> None:
        provider = make_provider(FakeKBRepo([]))

        bundle = await provider.fetch_context(uuid4())

        assert bundle.characters.text == ""
        assert bundle.factions.text == ""

    @pytest.mark.asyncio
    async def test_failing_rel_repo_degrades_relationships_only(self) -> None:
        """A relationship-store failure degrades only ``kb_relationships``."""
        provider = make_provider(FakeKBRepo(populated_entries()), FailingRelRepo())

        bundle = await provider.fetch_context(uuid4())

        # KB entities still render normally.
        assert bundle.characters.text != ""
        # Relationships degraded to empty (RULE-11), no exception propagated.
        assert bundle.relationships.text == ""

    @pytest.mark.asyncio
    async def test_none_rel_repo_yields_empty_relationships(self) -> None:
        provider = make_provider(FakeKBRepo(populated_entries()), None)

        bundle = await provider.fetch_context(uuid4())

        assert bundle.characters.text != ""
        assert bundle.relationships.text == ""


# ---------------------------------------------------------------------------
# fetch_world_context — delegation to the kb merge/extract aggregate
# ---------------------------------------------------------------------------


class TestFetchWorldContext:
    @pytest.mark.asyncio
    async def test_returns_world_context_for_populated_kb(self) -> None:
        provider = make_provider(FakeKBRepo([make_entry("Elara", "character")]))

        result = await provider.fetch_world_context(uuid4())

        assert result != ""
        assert "Elara" in result
        assert "character" in result

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_kb_repo(self) -> None:
        provider = make_provider(None)

        assert await provider.fetch_world_context(uuid4()) == ""

    @pytest.mark.asyncio
    async def test_returns_empty_on_empty_kb(self) -> None:
        provider = make_provider(FakeKBRepo([]))

        assert await provider.fetch_world_context(uuid4()) == ""
