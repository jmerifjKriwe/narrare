"""Tests for the count-based entity cap in ``format_entities``.

Mirrors the R1 relationship-cap suite (``test_relationship_format.py``,
``TestRelationshipEdgeCap``): below the cap the render is byte-identical
to the uncapped output (inert path); above it, the deterministic first-N
blocks (in caller order — ``format_entities`` does not sort) are rendered
plus an LLM-visible omission marker, while ``entry_count`` keeps reporting
the TOTAL pre-cap entity count (metadata = KB truth). The cap lives at the
core formatter so every caller (writing seams, ADR-067 provider slots,
chat ``kb_other``) inherits it uniformly — same choke-point rationale as
Ruling 1. RULE-11: the cap/marker never raise.
"""

from __future__ import annotations

from narrare_core.context._render_options import RenderOptions
from narrare_core.writing._helpers import DEFAULT_MAX_ENTITIES, format_entities
from narrare_core.writing.context_models import KBEntity


def _entities(count: int, *, uncertain: bool = False) -> list[KBEntity]:
    return [
        KBEntity(
            entity_id=f"ent-{i:03d}",
            entity_type="system",
            name=f"Entity {i:03d}",
            content=f"Body {i:03d}.",
            source="auto_extraction" if uncertain else "manual",
            review_status="pending" if uncertain else "endorsed",
            confidence=0.42 if uncertain else 1.0,
        )
        for i in range(count)
    ]


class TestEntityCap:
    """Count-based entity cap at the core formatter (chat kb_other follow-up).

    Same contract class as ``TestRelationshipEdgeCap`` (Ruling 1): inert
    below the cap, first-N + marker above it, ``entry_count`` = pre-cap
    total, empty input short-circuits, never raises.
    """

    def test_default_cap_is_50(self) -> None:
        """Pin the domain ceiling (RULE-18: Final, not configuration).

        50 (not the R1 relationship value 100): entity blocks render
        ``### Type: Name`` plus the full KB body — several times a one-line
        relationship edge — so the same unbudgeted-context token ceiling
        is reached at roughly half the entry count.
        """
        assert DEFAULT_MAX_ENTITIES == 50

    def test_below_cap_output_byte_identical_no_marker(self) -> None:
        """4 entities, explicit cap 50 → exact uncapped text, no marker."""
        result = format_entities(_entities(4), max_entities=50)
        assert result.text == (
            "### System: Entity 000\nBody 000.\n\n"
            "### System: Entity 001\nBody 001.\n\n"
            "### System: Entity 002\nBody 002.\n\n"
            "### System: Entity 003\nBody 003."
        )
        assert "omitted" not in result.text
        assert result.entry_count == 4

    def test_default_param_inherits_module_default_below_cap(self) -> None:
        """Omitting max_entities uses DEFAULT_MAX_ENTITIES (inert here)."""
        result = format_entities(_entities(4))
        assert "omitted" not in result.text
        assert result.entry_count == 4

    def test_exceed_cap_renders_first_n_plus_marker(self) -> None:
        """5 entities, cap 3 → first 3 blocks (caller order) + marker."""
        result = format_entities(_entities(5), max_entities=3)
        blocks = result.text.split("\n\n")
        assert len(blocks) == 4
        assert blocks[0] == "### System: Entity 000\nBody 000."
        assert blocks[2] == "### System: Entity 002\nBody 002."
        assert blocks[3] == "[… 2 more entities omitted]"
        # Deterministic first-N in caller order: Entity 003/004 are absent.
        assert "Entity 003" not in result.text
        assert "Entity 004" not in result.text
        assert result.entry_count == 5

    def test_at_cap_renders_all_no_marker(self) -> None:
        """Total == cap → all entities rendered, boundary has NO marker."""
        result = format_entities(_entities(3), max_entities=3)
        assert result.text.count("### ") == 3
        assert "omitted" not in result.text
        assert result.entry_count == 3

    def test_default_cap_truncates_at_50_with_marker(self) -> None:
        """55 entities, default cap → 50 rendered blocks + marker for 5."""
        result = format_entities(_entities(55))
        blocks = result.text.split("\n\n")
        assert len(blocks) == 51
        assert blocks[0] == "### System: Entity 000\nBody 000."
        assert blocks[49] == "### System: Entity 049\nBody 049."
        assert blocks[50] == "[… 5 more entities omitted]"
        assert "Entity 050" not in result.text
        # Metadata keeps the pre-cap total.
        assert result.entry_count == 55

    def test_entry_count_total_while_rendered_capped(self) -> None:
        """entry_count == total pre-cap even though .text holds N blocks."""
        result = format_entities(_entities(7), max_entities=4)
        assert result.entry_count == 7
        assert result.text.count("### ") == 4

    def test_marker_present_on_annotated_path(self) -> None:
        """Provenance-annotated renders (chat/planning) cap identically."""
        result = format_entities(
            _entities(5, uncertain=True),
            options=RenderOptions(annotate_provenance=True),
            max_entities=3,
        )
        assert result.text.count("### ") == 3
        assert "[… 2 more entities omitted]" in result.text
        assert result.entry_count == 5

    def test_empty_with_explicit_cap_unchanged(self) -> None:
        """Empty input short-circuits before the cap — text stays ''."""
        result = format_entities([], max_entities=3)
        assert result.text == ""
        assert result.entry_count == 0

    def test_zero_cap_renders_only_marker_never_raises(self) -> None:
        """Degenerate cap → everything omitted, marker only, no raise."""
        result = format_entities(_entities(2), max_entities=0)
        assert result.text == "[… 2 more entities omitted]"
        assert result.entry_count == 2
