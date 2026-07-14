"""Unit tests for context/_kb_envelope.py — KB Context Envelope contract.

Covers (ADR-050 P1-A — CR-AUFG-04-01):
1. ``RenderedKBContext`` — frozen, hashable, default values, accounting
2. ``KBContextSource`` — structural Protocol compatibility
3. ``KBContextEnvelope`` — structural Protocol compatibility
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING, Any, cast

import pytest

from narrare_core.context._kb_envelope import (
    KBContextEnvelope,
    KBContextSource,
    OmissionReason,
    ProvenanceField,
    RenderedKBContext,
)

if TYPE_CHECKING:
    from narrare_core.context._render_options import RenderOptions

# =====================================================================
# RenderedKBContext — dataclass behavior
# =====================================================================


class TestRenderedKBContextCreation:
    """RenderedKBContext construction and field access."""

    def test_creation_with_required_fields_only(self) -> None:
        result = RenderedKBContext(
            text="### Character: Alice\nA brave hero.",
            preserved_fields=frozenset({"provenance"}),
        )
        assert result.text == "### Character: Alice\nA brave hero."
        assert result.preserved_fields == frozenset({"provenance"})
        # Defaults
        assert result.omitted_fields == ()
        assert result.entry_count == 0
        assert result.render_path == ""

    def test_creation_with_all_fields(self) -> None:
        omitted: tuple[tuple[ProvenanceField, OmissionReason], ...] = (
            ("freshness", "tier_does_not_require"),
            ("evidence", "token_budget_exhausted"),
        )
        result = RenderedKBContext(
            text="### Character: Alice\nA brave hero.",
            preserved_fields=frozenset({"provenance", "review_state"}),
            omitted_fields=omitted,
            entry_count=3,
            render_path="writing._helpers.format_entities",
        )
        assert result.entry_count == 3
        assert result.render_path == "writing._helpers.format_entities"
        assert len(result.omitted_fields) == 2
        assert ("freshness", "tier_does_not_require") in result.omitted_fields
        assert ("evidence", "token_budget_exhausted") in result.omitted_fields

    def test_empty_text_is_valid(self) -> None:
        """Empty text is valid — happens when no entries were provided."""
        result = RenderedKBContext(text="", preserved_fields=frozenset())
        assert result.text == ""
        assert result.entry_count == 0

    def test_preserved_fields_accepts_all_provenance_literals(self) -> None:
        """Every ProvenanceField literal can appear in preserved_fields."""
        all_fields: frozenset[ProvenanceField] = frozenset(
            {
                "priority",
                "provenance",
                "review_state",
                "freshness",
                "evidence",
                "kb_lifecycle",
            }
        )
        result = RenderedKBContext(text="...", preserved_fields=all_fields)
        assert result.preserved_fields == all_fields

    def test_omitted_fields_accepts_all_omission_reasons(self) -> None:
        """Every OmissionReason literal can appear in omitted_fields."""
        all_reasons: tuple[tuple[ProvenanceField, OmissionReason], ...] = (
            ("priority", "token_budget_exhausted"),
            ("provenance", "tier_does_not_require"),
            ("review_state", "consumer_cannot_act"),
            ("freshness", "explicitly_suppressed_for_run"),
        )
        result = RenderedKBContext(
            text="...",
            preserved_fields=frozenset(),
            omitted_fields=all_reasons,
        )
        assert len(result.omitted_fields) == 4


class TestRenderedKBContextImmutability:
    """RenderedKBContext is frozen (immutable)."""

    def test_cannot_set_text(self) -> None:
        result = RenderedKBContext(text="original", preserved_fields=frozenset())
        with pytest.raises(FrozenInstanceError):
            cast("Any", result).text = "changed"

    def test_cannot_set_entry_count(self) -> None:
        result = RenderedKBContext(text="x", preserved_fields=frozenset())
        with pytest.raises(FrozenInstanceError):
            cast("Any", result).entry_count = 99

    def test_cannot_add_attribute(self) -> None:
        """slots=True prevents adding new attributes."""
        result = RenderedKBContext(text="x", preserved_fields=frozenset())
        with pytest.raises((AttributeError, TypeError)):
            cast("Any", result).extra = "unexpected"

    def test_has_no_dict_attribute(self) -> None:
        """Slots=True means no __dict__."""
        result = RenderedKBContext(text="x", preserved_fields=frozenset())
        assert not hasattr(result, "__dict__")


class TestRenderedKBContextHashability:
    """RenderedKBContext is hashable (usable as dict key / set member)."""

    def test_equal_instances_hash_equal(self) -> None:
        a = RenderedKBContext(text="x", preserved_fields=frozenset({"provenance"}))
        b = RenderedKBContext(text="x", preserved_fields=frozenset({"provenance"}))
        assert hash(a) == hash(b)

    def test_usable_in_set(self) -> None:
        a = RenderedKBContext(text="x", preserved_fields=frozenset({"provenance"}))
        b = RenderedKBContext(text="x", preserved_fields=frozenset({"provenance"}))
        c = RenderedKBContext(text="y", preserved_fields=frozenset())
        assert len({a, b, c}) == 2

    def test_usable_as_dict_key(self) -> None:
        result = RenderedKBContext(text="x", preserved_fields=frozenset())
        mapping: dict[RenderedKBContext, str] = {result: "value"}
        assert mapping[result] == "value"

    def test_different_omitted_fields_produce_different_hash(self) -> None:
        """omitted_fields participates in the hash."""
        a = RenderedKBContext(
            text="x",
            preserved_fields=frozenset(),
            omitted_fields=(("freshness", "tier_does_not_require"),),
        )
        b = RenderedKBContext(
            text="x",
            preserved_fields=frozenset(),
            omitted_fields=(("evidence", "token_budget_exhausted"),),
        )
        assert hash(a) != hash(b)

    def test_different_preserved_fields_produce_different_hash(self) -> None:
        a = RenderedKBContext(text="x", preserved_fields=frozenset({"provenance"}))
        b = RenderedKBContext(text="x", preserved_fields=frozenset({"freshness"}))
        assert hash(a) != hash(b)


# =====================================================================
# KBContextSource — structural Protocol compatibility
# =====================================================================


class _FakeKBEntry:
    """Fake satisfying KBContextSource structurally.

    Mirrors the shape of KBContextEntry (prompts/context.py) and
    KBEntity (writing/context_models.py) without importing them.
    """

    def __init__(
        self,
        entity_type: str = "character",
        name: str = "Alice",
        content: str = "A brave hero.",
        source: str = "curated",
        review_status: str = "canon",
        confidence: float = 0.95,
    ) -> None:
        self.entity_type = entity_type
        self.name = name
        self.content = content
        self.source = source
        self.review_status = review_status
        self.confidence = confidence


class _FakeKBEntryWithExtra(_FakeKBEntry):
    """Source types may carry additional fields beyond the Protocol shape."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.similarity_score: float = 0.88


class TestKBContextSourceProtocol:
    """KBContextSource is a @runtime_checkable structural Protocol."""

    def test_fake_entry_satisfies_protocol(self) -> None:
        entry = _FakeKBEntry()
        assert isinstance(entry, KBContextSource)

    def test_entry_with_extra_fields_still_satisfies(self) -> None:
        """Protocol is a lower bound — extra fields are allowed."""
        entry = _FakeKBEntryWithExtra()
        assert isinstance(entry, KBContextSource)

    def test_plain_object_does_not_satisfy(self) -> None:
        assert not isinstance(object(), KBContextSource)

    def test_dict_does_not_satisfy(self) -> None:
        """dict with the right keys is NOT structurally compatible —
        Protocol checks attributes, not dict keys."""
        d = {"entity_type": "character", "name": "Alice"}
        assert not isinstance(d, KBContextSource)


# =====================================================================
# KBContextEnvelope — structural Protocol compatibility
# =====================================================================


class _FakeHighFidelityRenderer:
    """Fake renderer preserving all provenance fields (tier-5 pinned)."""

    def render(
        self,
        entries: list[KBContextSource],
        *,
        tier: str,
        options: RenderOptions | None = None,
    ) -> RenderedKBContext:
        text = "\n".join(f"### {e.entity_type}: {e.name}\n{e.content}" for e in entries)
        return RenderedKBContext(
            text=text,
            preserved_fields=frozenset(
                {"provenance", "review_state", "freshness", "evidence", "kb_lifecycle", "priority"}
            ),
            omitted_fields=(),
            entry_count=len(entries),
            render_path="_FakeHighFidelityRenderer",
        )


class _FakeLowFidelityRenderer:
    """Fake renderer omitting some provenance fields (tier-1 immediate)."""

    def render(
        self,
        entries: list[KBContextSource],
        *,
        tier: str,
        options: RenderOptions | None = None,
    ) -> RenderedKBContext:
        text = "\n".join(f"### {e.entity_type}: {e.name}\n{e.content}" for e in entries)
        omitted: tuple[tuple[ProvenanceField, OmissionReason], ...] = (
            ("freshness", "tier_does_not_require"),
            ("evidence", "tier_does_not_require"),
            ("priority", "tier_does_not_require"),
            ("kb_lifecycle", "tier_does_not_require"),
        )
        return RenderedKBContext(
            text=text,
            preserved_fields=frozenset({"provenance", "review_state"}),
            omitted_fields=omitted,
            entry_count=len(entries),
            render_path="_FakeLowFidelityRenderer",
        )


class TestKBContextEnvelopeProtocol:
    """KBContextEnvelope is a @runtime_checkable structural Protocol."""

    def test_high_fidelity_renderer_satisfies_protocol(self) -> None:
        renderer = _FakeHighFidelityRenderer()
        assert isinstance(renderer, KBContextEnvelope)

    def test_low_fidelity_renderer_satisfies_protocol(self) -> None:
        renderer = _FakeLowFidelityRenderer()
        assert isinstance(renderer, KBContextEnvelope)

    def test_plain_object_does_not_satisfy(self) -> None:
        assert not isinstance(object(), KBContextEnvelope)

    @pytest.mark.asyncio
    async def test_high_fidelity_render_preserves_all_fields(self) -> None:
        """A high-fidelity renderer preserves all provenance fields."""
        renderer = _FakeHighFidelityRenderer()
        entries: list[KBContextSource] = [_FakeKBEntry(), _FakeKBEntry(name="Bob")]
        result = renderer.render(entries, tier="tier5_pinned")
        assert result.entry_count == 2
        assert len(result.omitted_fields) == 0
        assert "Alice" in result.text
        assert "Bob" in result.text
        assert result.render_path == "_FakeHighFidelityRenderer"

    @pytest.mark.asyncio
    async def test_low_fidelity_render_documents_omissions(self) -> None:
        """A low-fidelity renderer MUST document omissions (RULE-22)."""
        renderer = _FakeLowFidelityRenderer()
        entries: list[KBContextSource] = [_FakeKBEntry()]
        result = renderer.render(entries, tier="tier1_immediate")
        assert result.entry_count == 1
        assert len(result.omitted_fields) > 0
        # Every omission must have a reason
        for _field, reason in result.omitted_fields:
            assert reason in (
                "token_budget_exhausted",
                "tier_does_not_require",
                "consumer_cannot_act",
                "explicitly_suppressed_for_run",
            )

    def test_render_with_empty_entries_produces_empty_text(self) -> None:
        renderer = _FakeHighFidelityRenderer()
        result = renderer.render([], tier="tier5_pinned")
        assert result.text == ""
        assert result.entry_count == 0


# =====================================================================
# RenderedKBContext — string-protocol helpers (__str__, split, contains)
# =====================================================================


class TestRenderedKBContextStringProtocol:
    """``RenderedKBContext`` interoperates with str-only consumers."""

    def test_str_returns_prompt_bound_text(self) -> None:
        result = RenderedKBContext(
            text="### Character: Alice\nA brave hero.",
            preserved_fields=frozenset({"provenance"}),
        )
        assert str(result) == "### Character: Alice\nA brave hero."

    def test_split_delegates_to_text(self) -> None:
        result = RenderedKBContext(
            text="line one\nline two\nline three",
            preserved_fields=frozenset(),
        )
        assert result.split("\n") == ["line one", "line two", "line three"]
        assert result.split(sep=None, maxsplit=1) == ["line", "one\nline two\nline three"]

    def test_contains_checks_text(self) -> None:
        result = RenderedKBContext(
            text="### Character: Alice",
            preserved_fields=frozenset(),
        )
        assert "Alice" in result
        assert "Bob" not in result
