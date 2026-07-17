"""Unit tests for the extracted-event name→KB-entity ref resolver (PLAN-004 §7).

``resolve_extracted_refs`` is a pure helper that turns the
``character_names`` / ``location_name`` carried on an
:class:`ExtractedTemporalExpression` into the
``character_refs`` / ``location_ref`` wire shape persisted on a
``TimelineEvent``. Only names that resolve to a real KB entity are linked;
non-matches are omitted (a ref without a real entity id cannot be tracked by
the cross-feature ref-index — see ``consistency/ref_index.py``).

These tests use ``SimpleNamespace`` entities (the structural Protocol input is
ORM-agnostic), matching the established pattern in
``tests/unit/api/planning/test_timeline_kb_context.py::_entry``.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from narrare.planning._extracted_event_refs import resolve_extracted_refs


@dataclass(frozen=True, slots=True)
class _TestEntity:
    """Typed entity stand-in satisfying the resolver's read-only Protocol.

    A frozen dataclass exposes its attributes as read-only, matching the
    ``@property``-declared members of ``_ExtractedRefEntity`` (``SimpleNamespace``
    attributes are dynamic and invisible to the type checker)."""

    id: UUID
    name: str
    entity_type: str


def _entity(name: str, entity_type: str, *, eid: UUID | None = None) -> _TestEntity:
    """Build a typed entity stand-in with the structural shape the resolver reads."""
    return _TestEntity(id=eid or uuid4(), name=name, entity_type=entity_type)


class TestResolveExtractedRefsCharacters:
    """character_names → character_refs resolution."""

    def test_matching_names_populate_refs_with_id_and_name(self) -> None:
        """Each character_name that matches a KB entity emits {"id","name"}."""
        hero = _entity("Hero", "character")
        sage = _entity("Sage", "character")
        entities = [hero, sage, _entity("Castle", "location")]

        refs, _ = resolve_extracted_refs(
            character_names=["Hero", "Sage"],
            location_name="",
            entities=entities,
        )

        assert refs == [
            {"id": str(hero.id), "name": "Hero"},
            {"id": str(sage.id), "name": "Sage"},
        ]

    def test_non_matching_names_are_omitted(self) -> None:
        """A name with no matching KB entity is dropped (never proxy-padded)."""
        hero = _entity("Hero", "character")
        entities = [hero, _entity("Castle", "location")]

        refs, _ = resolve_extracted_refs(
            character_names=["Hero", "Ghost"],  # Ghost has no KB entity
            location_name="",
            entities=entities,
        )

        assert refs == [{"id": str(hero.id), "name": "Hero"}]

    def test_matching_is_case_insensitive_and_trim_insensitive(self) -> None:
        """Names match after lowercasing + whitespace trim."""
        hero = _entity("Hero", "character")
        entities = [hero]

        refs, _ = resolve_extracted_refs(
            character_names=["  hErO  "],
            location_name="",
            entities=entities,
        )

        assert refs == [{"id": str(hero.id), "name": "Hero"}]

    def test_duplicate_names_dedupe_by_entity_id(self) -> None:
        """The same name twice resolves to one ref (no duplicate links)."""
        hero = _entity("Hero", "character")
        entities = [hero]

        refs, _ = resolve_extracted_refs(
            character_names=["Hero", "hero"],
            location_name="",
            entities=entities,
        )

        assert refs == [{"id": str(hero.id), "name": "Hero"}]

    def test_emitted_name_uses_canonical_entity_name_not_input(self) -> None:
        """The ref carries the KB entity's stored name (canonical casing)."""
        hero = _entity("Hero of Time", "character")
        entities = [hero]

        refs, _ = resolve_extracted_refs(
            character_names=["hero of time"],
            location_name="",
            entities=entities,
        )

        assert refs == [{"id": str(hero.id), "name": "Hero of Time"}]


class TestResolveExtractedRefsLocation:
    """location_name → location_ref resolution."""

    def test_matching_location_name_yields_location_ref(self) -> None:
        """A matching location_name resolves to a single location_ref dict."""
        castle = _entity("Castle", "location")
        entities = [_entity("Hero", "character"), castle]

        _, location_ref = resolve_extracted_refs(
            character_names=[],
            location_name="Castle",
            entities=entities,
        )

        assert location_ref == {"id": str(castle.id), "name": "Castle"}

    def test_non_matching_location_name_yields_none(self) -> None:
        """No matching location → location_ref is None (no proxy)."""
        entities = [_entity("Hero", "character"), _entity("Castle", "location")]

        _, location_ref = resolve_extracted_refs(
            character_names=[],
            location_name="Nowhere",
            entities=entities,
        )

        assert location_ref is None

    def test_location_matching_is_case_and_trim_insensitive(self) -> None:
        """location_name matches after lowercasing + whitespace trim."""
        castle = _entity("Castle", "location")
        entities = [castle]

        _, location_ref = resolve_extracted_refs(
            character_names=[],
            location_name="  cAsTlE  ",
            entities=entities,
        )

        assert location_ref == {"id": str(castle.id), "name": "Castle"}

    def test_first_location_wins_when_multiple_share_a_name(self) -> None:
        """Ambiguous location names resolve deterministically to the first."""
        first = _entity("Tavern", "location")
        second = _entity("Tavern", "location")
        entities = [first, second]

        _, location_ref = resolve_extracted_refs(
            character_names=[],
            location_name="Tavern",
            entities=entities,
        )

        assert location_ref == {"id": str(first.id), "name": "Tavern"}


class TestResolveExtractedRefsEdgeCases:
    """Empty / None / whitespace inputs degrade to empty refs (RULE-11)."""

    def test_empty_character_names_yields_empty_refs(self) -> None:
        refs, _ = resolve_extracted_refs(
            character_names=[],
            location_name="",
            entities=[_entity("Hero", "character")],
        )
        assert refs == []

    def test_whitespace_only_names_are_treated_as_empty(self) -> None:
        """A name that is only whitespace never matches anything."""
        refs, location_ref = resolve_extracted_refs(
            character_names=["   ", ""],
            location_name="   ",
            entities=[_entity("Hero", "character"), _entity("Castle", "location")],
        )
        assert refs == []
        assert location_ref is None

    def test_no_entities_yields_empty_refs(self) -> None:
        """An empty KB degrades to empty refs / None location (no exception)."""
        refs, location_ref = resolve_extracted_refs(
            character_names=["Hero"],
            location_name="Castle",
            entities=[],
        )
        assert refs == []
        assert location_ref is None

    def test_only_non_character_non_location_entities_ignored(self) -> None:
        """faction/other entity types never become character or location refs."""
        refs, location_ref = resolve_extracted_refs(
            character_names=["Night Watch"],
            location_name="Night Watch",
            entities=[_entity("Night Watch", "faction")],
        )
        assert refs == []
        assert location_ref is None
