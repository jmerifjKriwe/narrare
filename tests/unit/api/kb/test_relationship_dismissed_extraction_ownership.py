"""S10 — IDOR regression tests: ownership gates on KB relationships + dismissed + extraction.

Before the S10 fix, all three services carried identity parameters that
never gated anything: ``RelationshipService.create``/``list_for_entry``/
``delete`` took ``user_id`` but only linked entries to the novel (any
caller of any novel could read, create, and delete the victim's
relationships); ``DismissedFindingService`` ignored the caller entirely
(a foreign caller could dismiss/un-dismiss findings and read the victim's
dismissed list — a foreign WRITE altering the victim's consistency
results); ``ExtractionService.extract_from_chapter`` claimed chapter
scoping "for ownership" while ``novel_id`` is not a user scope at all
(any caller could extract the victim's chapter with LLM analysis).

The fix (plan S10, Pattern B — reusing the S9 ``verify_novel_owned``
gate) raises ``NotFoundError`` at each public method entry BEFORE any
entry/relationship read or write, dismissal state change, chapter
content load, or LLM call — foreign ≡ unknown (anti-enumeration), both
404.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare_core.shared.errors import NotFoundError

from ._extraction_helpers import make_extraction_output
from ._test_fakes_relationship_dismissed_extraction import (
    FakeExtractionChapter,
    FakeRelEntry,
    FakeRelRow,
    make_dismissed_ownership_service,
    make_extraction_ownership_service,
    make_relationship_ownership_service,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from narrare_core.llm import ResolvedModelConfig

USER_A = uuid4()  # rightful owner of NOVEL_ID (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A
FOREIGN_NOVEL_ID = uuid4()  # owned by USER_B (a real novel — just not the caller's)

_OWNERSHIP = {NOVEL_ID: USER_A, FOREIGN_NOVEL_ID: USER_B}

_CHAPTER_ID = uuid4()
_ENTRY_ID = uuid4()
_REL_ID = uuid4()


def _rel_fixtures() -> tuple[list[FakeRelEntry], list[FakeRelRow]]:
    """Two entries in NOVEL_ID plus one relationship between them."""
    e1 = FakeRelEntry(id=_ENTRY_ID, novel_id=NOVEL_ID, name="Alice")
    e2 = FakeRelEntry(id=uuid4(), novel_id=NOVEL_ID, name="Bob")
    rel = FakeRelRow(id=_REL_ID, source_id=e1.id, target_id=e2.id)
    return [e1, e2], [rel]


# ---------------------------------------------------------------------------
# Relationships — create + list_for_entry + delete
# ---------------------------------------------------------------------------


class TestRelationshipOwnership:
    """All three relationship operations gate novel ownership first."""

    async def test_owner_create_returns_relationship(self) -> None:
        """Matrix case (1): the rightful owner's create is unchanged."""
        entries, _ = _rel_fixtures()
        service, entry_repo, rel_repo, novel_repo = make_relationship_ownership_service(
            _OWNERSHIP, entries
        )

        from narrare.kb.schemas import KBRelationshipCreate

        rel = await service.create(
            NOVEL_ID,
            USER_A,
            KBRelationshipCreate(
                source_id=entries[0].id,
                target_id=entries[1].id,
                rel_type="rival",
            ),
        )

        assert rel.rel_type == "rival"
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]
        assert len(rel_repo.create_calls) == 1
        assert entry_repo.get_by_id_calls == [entries[0].id, entries[1].id]

    async def test_foreign_novel_create_denied_before_any_write(self) -> None:
        """Matrix case (2)+(4): foreign novel → 404 BEFORE the entry loads,
        the duplicate check, or any KBRelationship row is created."""
        entries, _ = _rel_fixtures()
        service, entry_repo, rel_repo, _ = make_relationship_ownership_service(_OWNERSHIP, entries)

        from narrare.kb.schemas import KBRelationshipCreate

        with pytest.raises(NotFoundError, match="Novel"):
            await service.create(
                NOVEL_ID,
                USER_B,
                KBRelationshipCreate(
                    source_id=entries[0].id,
                    target_id=entries[1].id,
                    rel_type="rival",
                ),
            )

        assert entry_repo.get_by_id_calls == []
        assert rel_repo.exists_calls == []
        assert rel_repo.create_calls == []

    async def test_owner_list_for_entry_returns_relationships(self) -> None:
        """Matrix case (1): the rightful owner's list is unchanged."""
        entries, rels = _rel_fixtures()
        service, entry_repo, _rel_repo, novel_repo = make_relationship_ownership_service(
            _OWNERSHIP, entries, rels
        )

        result = await service.list_for_entry(NOVEL_ID, entries[0].id, USER_A)

        assert [r.id for r in result] == [rels[0].id]
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]
        assert entry_repo.get_by_id_calls == [entries[0].id]

    async def test_foreign_novel_list_denied_before_entry_load(self) -> None:
        """Matrix case (2)+(4): foreign novel → 404 BEFORE the entry is
        loaded or any relationship is listed — foreign entity ids are not
        enumerable either."""
        entries, rels = _rel_fixtures()
        service, entry_repo, rel_repo, _ = make_relationship_ownership_service(
            _OWNERSHIP, entries, rels
        )

        with pytest.raises(NotFoundError, match="Novel"):
            await service.list_for_entry(NOVEL_ID, entries[0].id, USER_B)

        assert entry_repo.get_by_id_calls == []
        assert rel_repo.list_for_entry_calls == []

    async def test_owner_delete_removes_relationship(self) -> None:
        """Matrix case (1): the rightful owner's delete is unchanged."""
        entries, rels = _rel_fixtures()
        service, _, rel_repo, novel_repo = make_relationship_ownership_service(
            _OWNERSHIP, entries, rels
        )

        await service.delete(NOVEL_ID, rels[0].id, USER_A)

        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]
        assert rel_repo.delete_calls == [rels[0]]

    async def test_foreign_novel_delete_denied_state_untouched(self) -> None:
        """Matrix case (2)+(4): foreign novel → 404 BEFORE the relationship
        is even fetched — the victim's relationship rows are untouched."""
        entries, rels = _rel_fixtures()
        service, entry_repo, rel_repo, _ = make_relationship_ownership_service(
            _OWNERSHIP, entries, rels
        )
        with pytest.raises(NotFoundError, match="Novel"):
            await service.delete(NOVEL_ID, rels[0].id, USER_B)

        assert rel_repo.get_by_id_calls == []
        assert rel_repo.delete_calls == []
        assert entry_repo.get_by_id_calls == []

    async def test_unknown_novel_indistinguishable_from_foreign(self) -> None:
        """Matrix case (3): unknown novel ≡ foreign novel."""
        entries, _ = _rel_fixtures()
        foreign_service, *_ = make_relationship_ownership_service(_OWNERSHIP, entries)
        unknown_service, *_ = make_relationship_ownership_service(_OWNERSHIP, entries)
        unknown_novel_id = uuid4()

        from narrare.kb.schemas import KBRelationshipCreate

        data = KBRelationshipCreate(
            source_id=entries[0].id, target_id=entries[1].id, rel_type="rival"
        )
        with pytest.raises(NotFoundError) as foreign_exc:
            await foreign_service.create(NOVEL_ID, USER_B, data)
        with pytest.raises(NotFoundError) as unknown_exc:
            await unknown_service.create(unknown_novel_id, USER_B, data)

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Novel ({NOVEL_ID}) not found"
        assert str(unknown_exc.value) == f"Novel ({unknown_novel_id}) not found"


# ---------------------------------------------------------------------------
# Dismissed findings — dismiss + list + undismiss
# ---------------------------------------------------------------------------


class TestDismissedOwnership:
    """All three dismissal operations gate novel ownership first."""

    async def test_owner_dismiss_returns_updated_list(self) -> None:
        """Matrix case (1): the rightful owner's dismiss is unchanged."""
        service, repo, novel_repo = make_dismissed_ownership_service(_OWNERSHIP)

        from narrare.kb.consistency_contracts import DismissFindingRequest

        result = await service.dismiss_finding(
            novel_id=NOVEL_ID,
            request=DismissFindingRequest(fingerprint="fp-1", reason="Accepted"),
            user_id=str(USER_A),
        )

        assert result.fingerprints == ["fp-1"]
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]
        assert repo.dismiss_calls == [(NOVEL_ID, "fp-1", "Accepted")]

    async def test_foreign_novel_dismiss_denied_state_untouched(self) -> None:
        """Matrix case (2)+(4): foreign novel → 404 BEFORE the DB dismiss,
        the mem0 forward, or the list re-read — a foreign WRITE must not
        alter the victim's consistency results."""
        service, repo, _ = make_dismissed_ownership_service(_OWNERSHIP)

        from narrare.kb.consistency_contracts import DismissFindingRequest

        with pytest.raises(NotFoundError, match="Novel"):
            await service.dismiss_finding(
                novel_id=NOVEL_ID,
                request=DismissFindingRequest(fingerprint="fp-1"),
                user_id=str(USER_B),
            )

        assert repo.dismiss_calls == []
        assert repo.list_calls == []

    async def test_owner_list_returns_fingerprints(self) -> None:
        """Matrix case (1): the rightful owner's list is unchanged."""
        service, repo, novel_repo = make_dismissed_ownership_service(
            _OWNERSHIP, novel_id=NOVEL_ID, fingerprints=["fp-1", "fp-2"]
        )

        result = await service.list_dismissed(novel_id=NOVEL_ID, user_id=str(USER_A))

        assert set(result.fingerprints) == {"fp-1", "fp-2"}
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]
        assert repo.list_calls == [NOVEL_ID]

    async def test_foreign_novel_list_denied_no_leak(self) -> None:
        """Matrix case (2)+(4): foreign novel → 404 BEFORE the dismissed
        list is read — the victim's dismissed fingerprints do not leak."""
        service, repo, _ = make_dismissed_ownership_service(_OWNERSHIP, fingerprints=["fp-secret"])

        with pytest.raises(NotFoundError, match="Novel"):
            await service.list_dismissed(novel_id=NOVEL_ID, user_id=str(USER_B))

        assert repo.list_calls == []

    async def test_owner_undismiss_returns_updated_list(self) -> None:
        """Matrix case (1): the rightful owner's un-dismiss is unchanged."""
        service, repo, novel_repo = make_dismissed_ownership_service(_OWNERSHIP)

        result = await service.undismiss_finding(
            novel_id=NOVEL_ID,
            fingerprint="fp-1",
            user_id=str(USER_A),
        )

        assert result.fingerprints == []
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]
        assert repo.undismiss_calls == [(NOVEL_ID, "fp-1")]

    async def test_foreign_novel_undismiss_denied_state_untouched(self) -> None:
        """Matrix case (2)+(4): foreign novel → 404 BEFORE the un-dismiss —
        a foreign caller cannot resurrect findings in the victim's results."""
        service, repo, _ = make_dismissed_ownership_service(_OWNERSHIP)

        with pytest.raises(NotFoundError, match="Novel"):
            await service.undismiss_finding(
                novel_id=NOVEL_ID,
                fingerprint="fp-1",
                user_id=str(USER_B),
            )

        assert repo.undismiss_calls == []
        assert repo.list_calls == []


# ---------------------------------------------------------------------------
# Extraction — extract_from_chapter
# ---------------------------------------------------------------------------


class TestExtractionOwnership:
    """``extract_from_chapter`` gates novel ownership before any load or LLM call."""

    @pytest.fixture
    def config(self) -> ResolvedModelConfig:
        from narrare_core.llm import ResolvedModelConfig

        return ResolvedModelConfig(
            provider_name="test", model_id="test-model", temperature=0.7, max_tokens=4096
        )

    async def test_owner_extract_returns_output(self, config: ResolvedModelConfig) -> None:
        """Matrix case (1): the rightful owner's extraction is unchanged."""
        from unittest.mock import AsyncMock, MagicMock, patch

        chapter = FakeExtractionChapter(id=_CHAPTER_ID)
        service, chapter_repo, kb_repo, registry, composer, novel_repo = (
            make_extraction_ownership_service(_OWNERSHIP, chapter, config)
        )

        with patch("narrare.kb.extraction_service.ExtractionAgent") as mock_agent_cls:
            mock_agent: MagicMock = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_extraction_output())
            mock_agent_cls.return_value = mock_agent

            result = await service.extract_from_chapter(
                novel_id=NOVEL_ID,
                chapter_id=_CHAPTER_ID,
                user_id=USER_A,
            )

        assert len(result.results) == 1
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]
        assert chapter_repo.get_by_id_calls == [(_CHAPTER_ID, NOVEL_ID)]
        assert kb_repo.list_entries_calls == [NOVEL_ID]
        assert registry.get_model_calls == 1
        assert len(composer.build_calls) >= 1
        mock_agent_cls.assert_called_once()

    async def test_foreign_novel_denied_before_content_load_and_llm(
        self, config: ResolvedModelConfig
    ) -> None:
        """Matrix case (2)+(4): foreign novel → 404 BEFORE the chapter
        content load, the KB dedup read, prompt composition, and the LLM
        run — no extraction result is returned."""
        from unittest.mock import AsyncMock, MagicMock, patch

        chapter = FakeExtractionChapter(id=_CHAPTER_ID)
        service, chapter_repo, kb_repo, registry, composer, _ = make_extraction_ownership_service(
            _OWNERSHIP, chapter, config
        )

        with patch("narrare.kb.extraction_service.ExtractionAgent") as mock_agent_cls:
            mock_agent: MagicMock = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_extraction_output())
            mock_agent_cls.return_value = mock_agent

            with pytest.raises(NotFoundError, match="Novel"):
                await service.extract_from_chapter(
                    novel_id=NOVEL_ID,
                    chapter_id=_CHAPTER_ID,
                    user_id=USER_B,
                )

        assert chapter_repo.get_by_id_calls == []
        assert kb_repo.list_entries_calls == []
        assert registry.get_model_calls == 0
        assert composer.build_calls == []
        mock_agent_cls.assert_not_called()

    async def test_unknown_novel_indistinguishable_from_foreign(
        self, config: ResolvedModelConfig
    ) -> None:
        """Matrix case (3): unknown novel ≡ foreign novel."""
        foreign_service, *_ = make_extraction_ownership_service(
            _OWNERSHIP, FakeExtractionChapter(id=_CHAPTER_ID), config
        )
        unknown_service, chapter_repo, *_ = make_extraction_ownership_service(
            _OWNERSHIP, FakeExtractionChapter(id=_CHAPTER_ID), config
        )
        unknown_novel_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await foreign_service.extract_from_chapter(
                novel_id=NOVEL_ID, chapter_id=_CHAPTER_ID, user_id=USER_B
            )
        with pytest.raises(NotFoundError) as unknown_exc:
            await unknown_service.extract_from_chapter(
                novel_id=unknown_novel_id, chapter_id=_CHAPTER_ID, user_id=USER_B
            )

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Novel ({NOVEL_ID}) not found"
        assert str(unknown_exc.value) == f"Novel ({unknown_novel_id}) not found"
        assert chapter_repo.get_by_id_calls == []
