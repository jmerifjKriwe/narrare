"""Tests for writing/context_wiki.py — wiki-aware entity formatting.

Unit tests (no I/O, no DB) for the ``format_entities_with_wiki`` helper
that decides between compressed wiki summaries and raw entity content.

Covers:
1. Empty entities → empty output
2. No wiki data → raw content fallback
3. Fresh wiki → compressed format with role + attributes
4. Stale/Pending wiki → raw content fallback with stale count
5. Mixed fresh/stale → correct counts per entity
6. Role and attributes included in wiki output
"""

from __future__ import annotations

from narrare_core.wiki.types import WikiSummaryData, WikiSummaryStatus
from narrare_core.writing.context_models import KBEntity
from narrare_core.writing.context_wiki import format_entities_with_wiki

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entity(
    entity_id: str = "ent-1",
    entity_type: str = "character",
    name: str = "Alice",
    content: str = "A brave warrior who hails from the northern mountains.",
) -> KBEntity:
    """Build a KBEntity with sensible defaults for wiki tests."""
    return KBEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        content=content,
    )


def _wiki(
    entity_id: str = "ent-1",
    narrative_summary: str = "Wiki summary for entity.",
    role_in_story: str | None = None,
    key_attributes: list[str] | None = None,
    status: WikiSummaryStatus = WikiSummaryStatus.FRESH,
) -> WikiSummaryData:
    """Build a WikiSummaryData with sensible defaults."""
    return WikiSummaryData(
        entity_id=entity_id,
        novel_id="novel-1",
        narrative_summary=narrative_summary,
        role_in_story=role_in_story,
        key_attributes=key_attributes or [],
        status=status,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFormatEntitiesWithWikiEmpty:
    """Empty entity list → empty string, zero counts."""

    def test_format_entities_with_wiki_empty(self) -> None:
        text, fresh, stale = format_entities_with_wiki([], None)
        assert text == ""
        assert fresh == 0
        assert stale == 0

    def test_format_entities_with_wiki_empty_with_wiki_dict(self) -> None:
        """Empty entities + non-empty wiki dict → still empty."""
        wikis = {"ent-1": _wiki("ent-1")}
        text, fresh, stale = format_entities_with_wiki([], wikis)
        assert text == ""
        assert fresh == 0
        assert stale == 0


class TestFormatEntitiesWithWikiNoSummaries:
    """No wiki data provided → raw content format used."""

    def test_format_entities_with_wiki_no_summaries_none(self) -> None:
        entities = [_entity("char-1", "character", "Alice", "A brave warrior.")]
        text, fresh, stale = format_entities_with_wiki(entities, None)
        assert fresh == 0
        assert stale == 0
        assert "A brave warrior." in text
        assert "Alice" in text

    def test_format_entities_with_wiki_no_summaries_empty_dict(self) -> None:
        entities = [_entity("char-1", "character", "Alice", "A brave warrior.")]
        text, fresh, stale = format_entities_with_wiki(entities, {})
        assert fresh == 0
        assert stale == 0
        assert "A brave warrior." in text

    def test_format_entities_with_wiki_no_matching_summary(self) -> None:
        """Wiki dict exists but has no entry for this entity → raw fallback."""
        entities = [_entity("char-1", "character", "Alice", "A brave warrior.")]
        wikis = {"other-entity": _wiki("other-entity")}
        text, fresh, stale = format_entities_with_wiki(entities, wikis)
        assert fresh == 0
        assert stale == 0
        assert "A brave warrior." in text


class TestFormatEntitiesWithWikiFresh:
    """Fresh wiki summary → compressed format used."""

    def test_format_entities_with_wiki_fresh_summary(self) -> None:
        entities = [_entity("char-1", "character", "Alice", "A brave warrior.")]
        wikis = {
            "char-1": _wiki(
                "char-1",
                narrative_summary="A fierce northern warrior.",
                role_in_story="Protagonist",
                key_attributes=["brave", "strong"],
                status=WikiSummaryStatus.FRESH,
            ),
        }
        text, fresh, stale = format_entities_with_wiki(entities, wikis)
        assert fresh == 1
        assert stale == 0
        # Wiki summary used, not raw content
        assert "A fierce northern warrior." in text
        assert "A brave warrior." not in text
        # Header still present
        assert "Alice" in text

    def test_fresh_without_role_or_attributes(self) -> None:
        """Fresh wiki with no role/attributes → summary only."""
        entities = [_entity("char-1", "character", "Alice", "Raw content.")]
        wikis = {
            "char-1": _wiki(
                "char-1",
                narrative_summary="Compressed summary.",
                status=WikiSummaryStatus.FRESH,
            ),
        }
        text, fresh, _stale = format_entities_with_wiki(entities, wikis)
        assert fresh == 1
        assert "Compressed summary." in text
        assert "Role:" not in text
        assert "Attributes:" not in text


class TestFormatEntitiesWithWikiStale:
    """Stale wiki → raw content fallback with stale count."""

    def test_format_entities_with_wiki_stale_summary(self) -> None:
        entities = [_entity("char-1", "character", "Alice", "A brave warrior.")]
        wikis = {
            "char-1": _wiki(
                "char-1",
                narrative_summary="Old wiki summary.",
                status=WikiSummaryStatus.STALE,
            ),
        }
        text, fresh, stale = format_entities_with_wiki(entities, wikis)
        assert fresh == 0
        assert stale == 1
        # Raw content used, not wiki
        assert "A brave warrior." in text
        assert "Old wiki summary." not in text

    def test_format_entities_with_wiki_pending_summary(self) -> None:
        entities = [_entity("char-1", "character", "Alice", "A brave warrior.")]
        wikis = {
            "char-1": _wiki(
                "char-1",
                narrative_summary="Pending wiki summary.",
                status=WikiSummaryStatus.PENDING,
            ),
        }
        text, fresh, stale = format_entities_with_wiki(entities, wikis)
        assert fresh == 0
        assert stale == 1
        assert "A brave warrior." in text
        assert "Pending wiki summary." not in text


class TestFormatEntitiesWithWikiMixed:
    """Mix of fresh/stale entities → correct counts."""

    def test_format_entities_with_wiki_mixed(self) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "Raw Alice content."),
            _entity("char-2", "character", "Bob", "Raw Bob content."),
            _entity("loc-1", "location", "Castle", "Raw castle content."),
        ]
        wikis = {
            "char-1": _wiki(
                "char-1", narrative_summary="Fresh Alice.", status=WikiSummaryStatus.FRESH
            ),
            "char-2": _wiki(
                "char-2", narrative_summary="Stale Bob.", status=WikiSummaryStatus.STALE
            ),
            # loc-1 has no wiki entry at all
        }
        text, fresh, stale = format_entities_with_wiki(entities, wikis)
        assert fresh == 1
        assert stale == 1
        # Alice uses wiki
        assert "Fresh Alice." in text
        assert "Raw Alice content." not in text
        # Bob falls back to raw
        assert "Raw Bob content." in text
        assert "Stale Bob." not in text
        # Castle has no wiki → raw
        assert "Raw castle content." in text

    def test_all_fresh(self) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "Raw Alice."),
            _entity("char-2", "character", "Bob", "Raw Bob."),
        ]
        wikis = {
            "char-1": _wiki(
                "char-1", narrative_summary="Wiki Alice.", status=WikiSummaryStatus.FRESH
            ),
            "char-2": _wiki(
                "char-2", narrative_summary="Wiki Bob.", status=WikiSummaryStatus.FRESH
            ),
        }
        text, fresh, stale = format_entities_with_wiki(entities, wikis)
        assert fresh == 2
        assert stale == 0
        assert "Wiki Alice." in text
        assert "Wiki Bob." in text

    def test_all_stale(self) -> None:
        entities = [
            _entity("char-1", "character", "Alice", "Raw Alice."),
            _entity("char-2", "character", "Bob", "Raw Bob."),
        ]
        wikis = {
            "char-1": _wiki(
                "char-1", narrative_summary="Wiki Alice.", status=WikiSummaryStatus.STALE
            ),
            "char-2": _wiki(
                "char-2", narrative_summary="Wiki Bob.", status=WikiSummaryStatus.PENDING
            ),
        }
        text, fresh, stale = format_entities_with_wiki(entities, wikis)
        assert fresh == 0
        assert stale == 2
        assert "Raw Alice." in text
        assert "Raw Bob." in text


class TestFormatEntitiesWithWikiRoleAndAttributes:
    """Role and key_attributes are included in wiki output."""

    def test_format_entities_with_wiki_includes_role(self) -> None:
        entities = [_entity("char-1", "character", "Alice", "Raw content.")]
        wikis = {
            "char-1": _wiki(
                "char-1",
                narrative_summary="A fierce warrior.",
                role_in_story="Protagonist and leader",
                status=WikiSummaryStatus.FRESH,
            ),
        }
        text, fresh, _stale = format_entities_with_wiki(entities, wikis)
        assert fresh == 1
        assert "Role: Protagonist and leader" in text

    def test_format_entities_with_wiki_includes_attributes(self) -> None:
        entities = [_entity("char-1", "character", "Alice", "Raw content.")]
        wikis = {
            "char-1": _wiki(
                "char-1",
                narrative_summary="A fierce warrior.",
                key_attributes=["brave", "loyal", "strategic"],
                status=WikiSummaryStatus.FRESH,
            ),
        }
        text, fresh, _stale = format_entities_with_wiki(entities, wikis)
        assert fresh == 1
        assert "Attributes: brave, loyal, strategic" in text

    def test_role_and_attributes_together(self) -> None:
        entities = [_entity("char-1", "character", "Alice", "Raw content.")]
        wikis = {
            "char-1": _wiki(
                "char-1",
                narrative_summary="A fierce warrior.",
                role_in_story="Main hero",
                key_attributes=["brave"],
                status=WikiSummaryStatus.FRESH,
            ),
        }
        text, _fresh, _stale = format_entities_with_wiki(entities, wikis)
        assert "Role: Main hero" in text
        assert "Attributes: brave" in text
        assert "A fierce warrior." in text

    def test_header_uses_entity_type(self) -> None:
        """Header format is '### Type: Name'."""
        entities = [_entity("loc-1", "location", "Castle", "A fortress.")]
        wikis = {
            "loc-1": _wiki(
                "loc-1",
                narrative_summary="An ancient stronghold.",
                status=WikiSummaryStatus.FRESH,
            ),
        }
        text, _fresh, _stale = format_entities_with_wiki(entities, wikis)
        assert "### Location: Castle" in text

    def test_stale_does_not_include_role(self) -> None:
        """When wiki is stale, role/attributes are NOT rendered — raw content used."""
        entities = [_entity("char-1", "character", "Alice", "Raw content.")]
        wikis = {
            "char-1": _wiki(
                "char-1",
                narrative_summary="Old wiki.",
                role_in_story="Protagonist",
                key_attributes=["brave"],
                status=WikiSummaryStatus.STALE,
            ),
        }
        text, _fresh, _stale = format_entities_with_wiki(entities, wikis)
        assert "Role: Protagonist" not in text
        assert "Attributes: brave" not in text
        assert "Raw content." in text
