"""Unit tests for the reusable KB-context provider — provenance, mapping,
and Protocol compliance (ADR-067).

This module is the second half of the split KB-context provider test suite
(extracted to respect the 400-line test file-size limit, RULE-04). It covers:

* provenance accounting (``RenderOptions(annotate_provenance=True)`` →
  non-empty ``preserved_fields`` + inline bracket, FIND-017);
* ``to_prompt_variables()`` mapping to the registered ``kb_*`` keys;
* ``KBContextProvider`` satisfies ``KBContextProviderProtocol`` (RULE-03).

Fetch/render behavior and RULE-11 degradation live in
``test_kb_context_provider.py``. Shared test doubles come from
``_kb_context_helpers``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.kb.context_contracts import KBContextBundle, KBContextProviderProtocol
from narrare_core.context._render_options import RenderOptions
from tests.unit.api.kb._kb_context_helpers import (
    FakeKBRepo,
    make_entry,
    make_provider,
    populated_entries,
)

# ---------------------------------------------------------------------------
# fetch_context — provenance accounting (FIND-017 / RULE-22)
# ---------------------------------------------------------------------------


class TestFetchContextProvenance:
    @pytest.mark.asyncio
    async def test_annotate_provenance_preserves_fields_for_pending_entry(self) -> None:
        """Non-manual + pending review → inline bracket + non-empty
        ``preserved_fields`` (provenance + review_state rendered)."""
        entries = [
            make_entry(
                "Whisper",
                "character",
                body="A rumoured figure.",
                source="auto_extraction",
                review_status="pending",
            )
        ]
        provider = make_provider(FakeKBRepo(entries))

        bundle = await provider.fetch_context(
            uuid4(), options=RenderOptions(annotate_provenance=True)
        )

        # Provenance accounting: the bracket rendered provenance + review_state.
        assert bundle.characters.preserved_fields  # non-empty
        assert "provenance" in bundle.characters.preserved_fields
        assert "review_state" in bundle.characters.preserved_fields
        # The inline bracket appears in the prompt-bound text.
        assert "pending review" in bundle.characters.text

    @pytest.mark.asyncio
    async def test_manual_entry_suppressed_even_when_annotating(self) -> None:
        """Manual-source entries are always suppressed (no bracket)."""
        entries = [make_entry("Elara", "character", source="manual", review_status="approved")]
        provider = make_provider(FakeKBRepo(entries))

        bundle = await provider.fetch_context(
            uuid4(), options=RenderOptions(annotate_provenance=True)
        )

        assert bundle.characters.preserved_fields == frozenset()
        assert "pending review" not in bundle.characters.text

    @pytest.mark.asyncio
    async def test_default_options_yield_no_annotation(self) -> None:
        """Without ``annotate_provenance`` the output is byte-for-byte legacy."""
        entries = [
            make_entry(
                "Whisper",
                "character",
                source="auto_extraction",
                review_status="pending",
            )
        ]
        provider = make_provider(FakeKBRepo(entries))

        bundle = await provider.fetch_context(uuid4())  # default options

        assert bundle.characters.preserved_fields == frozenset()
        assert "pending review" not in bundle.characters.text
        # render_options carried on the bundle for audit (RULE-22).
        assert bundle.render_options.annotate_provenance is False

    @pytest.mark.asyncio
    async def test_render_options_reflected_on_bundle(self) -> None:
        entries = [make_entry("Elara", "character")]
        provider = make_provider(FakeKBRepo(entries))
        opts = RenderOptions(annotate_provenance=True)

        bundle = await provider.fetch_context(uuid4(), options=opts)

        assert bundle.render_options is opts


# ---------------------------------------------------------------------------
# to_prompt_variables — kb_* mapping
# ---------------------------------------------------------------------------


class TestToPromptVariables:
    @pytest.mark.asyncio
    async def test_maps_to_kb_keys_non_empty_on_populated_kb(self) -> None:
        provider = make_provider(FakeKBRepo(populated_entries()))

        bundle = await provider.fetch_context(uuid4())
        variables = bundle.to_prompt_variables()

        assert set(variables) == {
            "kb_characters",
            "kb_locations",
            "kb_factions",
            "kb_relationships",
        }
        assert variables["kb_characters"] != ""
        assert "Elara" in variables["kb_characters"]
        assert variables["kb_locations"] != ""
        assert variables["kb_factions"] != ""
        # No rel repo wired → relationships empty.
        assert variables["kb_relationships"] == ""

    def test_empty_bundle_maps_to_empty_strings(self) -> None:
        variables = KBContextBundle.empty().to_prompt_variables()

        assert set(variables) == {
            "kb_characters",
            "kb_locations",
            "kb_factions",
            "kb_relationships",
        }
        assert all(v == "" for v in variables.values())


# ---------------------------------------------------------------------------
# Protocol compliance (RULE-03)
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_provider_satisfies_protocol(self) -> None:
        provider = make_provider(None)

        assert isinstance(provider, KBContextProviderProtocol)

    def test_empty_bundle_is_a_kb_context_bundle(self) -> None:
        bundle = KBContextBundle.empty()

        assert isinstance(bundle, KBContextBundle)
