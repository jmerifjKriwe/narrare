"""Tests für KB-Format-Helfer — Formatierungslogik (kein I/O).

Test-Strategie:
- Reine Funktionstests, keine Agent- oder LLM-Interaktion
- SimpleNamespace als einfache Test-Dummies (getattr-basiert)
"""

from __future__ import annotations

from types import SimpleNamespace

from narrare_core.agents.kb_formatters import (
    format_entries,
    format_entity,
    format_related,
)

# ---------------------------------------------------------------------------
# A. format_entries
# ---------------------------------------------------------------------------


class TestFormatEntries:
    """A. format_entries — Liste von KB-Einträgen formatieren."""

    def test_format_entries_empty(self) -> None:
        """Leere Liste → nur Header ohne Bullets."""
        result = format_entries([])
        assert result == "Found KB entries:"

    def test_format_entries_with_data(self) -> None:
        """Listet Einträge mit Name, Typ, Body-Preview."""
        entries = [
            SimpleNamespace(
                name="Anna Mueller",
                entity_type="character",
                body="A brave warrior from the north.",
            ),
            SimpleNamespace(
                name="Berlin",
                entity_type="location",
                body="A large city with a dark secret.",
            ),
        ]
        result = format_entries(entries)
        assert "Anna Mueller" in result
        assert "[character]" in result
        assert "A brave warrior" in result
        assert "Berlin" in result
        assert "[location]" in result
        assert result.startswith("Found KB entries:")

    def test_format_entries_truncates_body(self) -> None:
        """Body wird auf 200 Zeichen gekürzt."""
        long_body = "A" * 500
        entries = [SimpleNamespace(name="Test", entity_type="concept", body=long_body)]
        result = format_entries(entries)
        assert "A" * 200 in result
        assert "A" * 201 not in result  # Gekürzt

    def test_format_entries_fallback_name(self) -> None:
        """Ohne name-Attribut → str(e) als Fallback (repr)."""
        entry = SimpleNamespace(entity_type="unknown")
        result = format_entries([entry])
        # str(SimpleNamespace(...)) enthält entity_type
        assert "(no content)" in result
        assert result.startswith("Found KB entries:")

    def test_format_entries_no_body(self) -> None:
        """Eintrag ohne body/description → '(no content)'."""
        entry = SimpleNamespace(name="Ghost", entity_type="concept")
        result = format_entries([entry])
        assert "(no content)" in result

    def test_format_entries_shows_more_for_over_10(self) -> None:
        """>10 Einträge → '... and X more entries'."""
        entries = [SimpleNamespace(name=f"E{i}", entity_type="type", body="x") for i in range(15)]
        result = format_entries(entries)
        assert "... and 5 more entries" in result


# ---------------------------------------------------------------------------
# B. format_entity
# ---------------------------------------------------------------------------


class TestFormatEntity:
    """B. format_entity — Einzelne Entity formatieren."""

    def test_format_entity_full(self) -> None:
        """Entity mit allen Feldern."""
        entity = SimpleNamespace(
            name="Anna Mueller",
            entity_type="character",
            body="A detailed backstory.",
            tags=["protagonist", "warrior"],
            status="published",
        )
        result = format_entity(entity)
        assert "Entity: Anna Mueller" in result
        assert "Type: character" in result
        assert "Status: published" in result
        assert "Tags: protagonist, warrior" in result
        assert "A detailed backstory." in result

    def test_format_entity_minimal(self) -> None:
        """Entity ohne body → kein Content-Block."""
        entity = SimpleNamespace(
            name="Mystery Box",
            entity_type="object",
        )
        result = format_entity(entity)
        assert "Entity: Mystery Box" in result
        assert "Type: object" in result
        assert "(no content)" not in result  # Kein body → kein Content-Block
        assert "Content:" not in result  # Kein Content-Block wenn body fehlt

    def test_format_entity_no_tags(self) -> None:
        """Entity ohne Tags → keine Tags-Zeile."""
        entity = SimpleNamespace(
            name="Simple",
            entity_type="concept",
            body="Just a concept.",
        )
        result = format_entity(entity)
        assert "Tags:" not in result

    def test_format_entity_uses_description_fallback(self) -> None:
        """Ohne body → description als Fallback."""
        entity = SimpleNamespace(
            name="Fallback",
            entity_type="location",
            description="A description.",
        )
        result = format_entity(entity)
        assert "A description." in result


# ---------------------------------------------------------------------------
# C. format_related
# ---------------------------------------------------------------------------


class TestFormatRelated:
    """C. format_related — Verwandte Entitäten formatieren."""

    def test_format_related_empty(self) -> None:
        """Keine Relationen → nur Header (keine Bullets)."""
        result = format_related("Anna", [])
        assert result == "Entities related to 'Anna':"

    def test_format_related_with_relations(self) -> None:
        """Listet verwandte Entitäten."""
        relations = [
            SimpleNamespace(target_name="Peter", rel_type="ally"),
            SimpleNamespace(target_name="Berlin", rel_type="lives_in"),
        ]
        result = format_related("Anna", relations)
        assert "Entities related to 'Anna'" in result
        assert "Peter (ally)" in result
        assert "Berlin (lives_in)" in result

    def test_format_related_truncates_at_15(self) -> None:
        """Maximal 15 Relationen."""
        relations = [SimpleNamespace(target_name=f"E{i}", rel_type="related") for i in range(20)]
        result = format_related("Source", relations)
        # Nur 15 Zeilen + 1 Header = 16 Zeilen
        assert len(result.split("\n")) == 16
        assert "E14" in result  # 15. Eintrag (0-indexed: 14)
        assert "E15" not in result  # 16. Eintrag (0-indexed: 15)

    def test_format_related_fallback_attrs(self) -> None:
        """Ohne target_name/rel_type → Fallbacks."""
        relation = SimpleNamespace()
        result = format_related("X", [relation])
        # Kein target_name → str(relation) genutzt
        assert "related" in result  # rel_type fallback
