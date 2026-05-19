"""Tests for @Name reference resolution.

Covers regex matching, service-level resolution, and repository
name lookups.  Uses mocked repos to avoid DB round-trips.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.kb._utils import MENTION_RE
from narrare.kb.contracts import KBRepositoryProtocol
from narrare.kb.models import KBEntry
from narrare.kb.schemas import ResolveReferencesResponse
from narrare.kb.service import KBService
from narrare.novels.contracts import NovelRepositoryProtocol
from narrare.novels.models import Novel
from narrare_core.shared.errors import ForbiddenError

# ---------------------------------------------------------------------------
# Regex tests
# ---------------------------------------------------------------------------


class TestMentionRegex:
    """Verify MENTION_RE correctly extracts @Name mentions."""

    def test_simple_name(self) -> None:
        matches = MENTION_RE.findall("Hello @Anna Müller, how are you?")
        assert "Anna Müller" in matches

    def test_no_match_for_email(self) -> None:
        matches = MENTION_RE.findall("Contact me at user@example.com")
        assert len(matches) == 0

    def test_multiple_mentions(self) -> None:
        matches = MENTION_RE.findall("@Anna and @Max and @Lena")
        assert set(matches) == {"Anna", "Max", "Lena"}

    def test_mention_at_start(self) -> None:
        matches = MENTION_RE.findall("@Protagonist walked in.")
        assert "Protagonist" in matches

    def test_mention_in_quotes(self) -> None:
        matches = MENTION_RE.findall('"@Anna Müller" is mentioned.')
        assert "Anna Müller" in matches

    def test_mention_with_hyphen(self) -> None:
        matches = MENTION_RE.findall("Met @Jean-Pierre today.")
        assert "Jean-Pierre" in matches

    def test_mention_with_apostrophe(self) -> None:
        matches = MENTION_RE.findall("@O'Brien is here.")
        assert "O'Brien" in matches

    def test_no_false_positive_at_end_of_word(self) -> None:
        matches = MENTION_RE.findall("The price is 5@ per item")
        assert len(matches) == 0

    def test_mention_with_german_umlaut(self) -> None:
        matches = MENTION_RE.findall("@Müller Straße ist lang.")
        assert "Müller Straße" in matches

    def test_mention_at_end_of_string(self) -> None:
        matches = MENTION_RE.findall("Talk to @Karl")
        assert "Karl" in matches

    def test_mention_only(self) -> None:
        matches = MENTION_RE.findall("@Anna")
        assert "Anna" in matches

    def test_empty_text(self) -> None:
        matches = MENTION_RE.findall("")
        assert len(matches) == 0

    def test_no_mention(self) -> None:
        matches = MENTION_RE.findall("Just some text without names.")
        assert len(matches) == 0


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


def _make_mock_entry(
    name: str,
    slug: str | None = None,
    entity_type: str = "character",
) -> MagicMock:
    """Create a mock KBEntry with the given attributes."""
    entry = MagicMock(spec=KBEntry)
    entry.id = uuid.uuid4()
    entry.name = name
    entry.slug = slug or name.lower().replace(" ", "-")
    entry.entity_type = entity_type
    entry.novel_id = uuid.uuid4()
    return entry


def _make_service(
    novel_owned: bool = True,
) -> tuple[KBService, AsyncMock]:
    """Create a KBService with mock repos."""
    repo = AsyncMock(spec=KBRepositoryProtocol)
    novel_repo = AsyncMock(spec=NovelRepositoryProtocol)

    if novel_owned:
        novel_repo.get_by_id = AsyncMock(return_value=MagicMock(spec=Novel))
    else:
        novel_repo.get_by_id = AsyncMock(return_value=None)

    service = KBService(repo=repo, novel_repo=novel_repo)
    return service, repo


class TestKBServiceResolveReferences:
    """Test service-level reference resolution."""

    async def test_resolve_known_mention(self) -> None:
        """Happy path: mention matches a KB entry."""
        service, repo = _make_service()
        entry = _make_mock_entry("Anna Müller")
        repo.get_by_name = AsyncMock(return_value=entry)

        result = await service.resolve_references(uuid.uuid4(), uuid.uuid4(), "Hello @Anna Müller!")

        assert isinstance(result, ResolveReferencesResponse)
        assert len(result.resolved) == 1
        assert result.resolved[0].mention == "Anna Müller"
        assert result.resolved[0].entry_id == str(entry.id)
        assert result.resolved[0].entry_name == "Anna Müller"
        assert result.resolved[0].entity_type == "character"
        assert result.resolved[0].slug == "anna-müller"
        assert result.html is not None
        assert 'href="/studio/' in result.html
        assert "kb-mention" in result.html

    async def test_resolve_unknown_mention(self) -> None:
        """Mention without matching entry returns unresolved reference."""
        service, repo = _make_service()
        repo.get_by_name = AsyncMock(return_value=None)

        result = await service.resolve_references(
            uuid.uuid4(), uuid.uuid4(), "@UnknownPerson was here."
        )

        assert len(result.resolved) == 1
        assert result.resolved[0].mention == "UnknownPerson"
        assert result.resolved[0].entry_id is None
        assert result.resolved[0].entry_name is None
        # HTML should leave @UnknownPerson unchanged
        assert result.html is not None
        assert "@UnknownPerson" in result.html

    async def test_resolve_multiple_mentions(self) -> None:
        """Multiple @mentions, some resolved, some not."""
        service, repo = _make_service()
        anna = _make_mock_entry("Anna")
        repo.get_by_name = AsyncMock(
            side_effect=lambda novel_id, name: {
                "Anna": anna,
            }.get(name)
        )

        result = await service.resolve_references(
            uuid.uuid4(), uuid.uuid4(), "@Anna and @Max and @Lena"
        )

        mentions = {r.mention: r.entry_id for r in result.resolved}
        assert mentions["Anna"] == str(anna.id)
        assert mentions["Max"] is None
        assert mentions["Lena"] is None

    async def test_resolve_deduplicates_mentions(self) -> None:
        """Same @mention appearing twice should only be resolved once."""
        service, repo = _make_service()
        anna = _make_mock_entry("Anna")
        repo.get_by_name = AsyncMock(return_value=anna)

        result = await service.resolve_references(
            uuid.uuid4(), uuid.uuid4(), "@Anna is here. @Anna is also there."
        )

        assert len(result.resolved) == 1

    async def test_resolve_no_mentions(self) -> None:
        """Text without @mentions returns empty result."""
        service, _ = _make_service()

        result = await service.resolve_references(
            uuid.uuid4(), uuid.uuid4(), "Plain text without mentions."
        )

        assert len(result.resolved) == 0
        assert result.html == "Plain text without mentions."

    async def test_resolve_forbidden_novel(self) -> None:
        """Raises ForbiddenError if user doesn't own the novel."""
        service, _ = _make_service(novel_owned=False)

        with pytest.raises(ForbiddenError):
            await service.resolve_references(uuid.uuid4(), uuid.uuid4(), "@Anna")

    async def test_resolve_empty_text(self) -> None:
        """Empty text returns empty result."""
        service, _ = _make_service()

        result = await service.resolve_references(uuid.uuid4(), uuid.uuid4(), "")

        assert len(result.resolved) == 0
        assert result.html == ""


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


class TestKBRepositoryNameLookup:
    """Test repository name-based queries against real DB schema.

    These use mocks since we're testing the query construction logic.
    """

    async def test_get_by_name_calls_ilike(self) -> None:
        """Verify get_by_name constructs an ILIKE query."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock(spec=["scalar_one_or_none"])
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        from narrare.kb.repository import KBRepository

        kb_repo = KBRepository(session=mock_session)  # type: ignore[arg-type]
        result = await kb_repo.get_by_name(uuid.uuid4(), "Anna Müller")
        assert result is None
        mock_session.execute.assert_awaited_once()

    async def test_search_by_name_prefix(self) -> None:
        """Verify search_by_name_prefix constructs an ILIKE prefix query."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock(spec=["scalars"])
        mock_result.scalars.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        from narrare.kb.repository import KBRepository

        kb_repo = KBRepository(session=mock_session)  # type: ignore[arg-type]
        result = await kb_repo.search_by_name_prefix(uuid.uuid4(), "An", limit=5)
        assert result == []
        mock_session.execute.assert_awaited_once()
