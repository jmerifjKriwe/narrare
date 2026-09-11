"""S9 — IDOR regression tests: ownership gates on KB graph + suggest + consistency (service).

Before the S9 fix, all three services carried identity parameters that
never gated anything: ``GraphService.get_graph``/``get_shortest_path``
took ``user_id`` "(for authorization)" but read the novel's entries,
relationships, and adjacency regardless of the caller;
``KBSuggestService.get_suggestions`` resolved only chapter∈novel (any
caller of any novel got suggestions over the victim's chapter content
and entity metadata); ``KBConsistencyService.check`` used ``user_id``
solely to scope mem0 suppression while all three analysis phases ran
over the foreign novel.

The fix (plan S9, Pattern B) is a service-entry gate
``novel_repo.get_by_id(novel_id, user_id)`` → ``NotFoundError`` BEFORE
any data load, cache probe, or LLM call — foreign ≡ unknown
(anti-enumeration), both 404.

The HTTP-level matrix (all 4 endpoints) lives in
``test_graph_suggest_consistency_ownership_api.py`` (RULE-04 split).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.kb.consistency_contracts import ConsistencyCheckRequest
from narrare_core.shared.errors import NotFoundError

from ._test_fakes_graph_suggest_consistency import (
    FakeGraphEntry,
    FakeGraphRelationship,
    FakeSuggestChapter,
    make_consistency_ownership_service,
    make_graph_ownership_service,
    make_suggest_ownership_service,
)

USER_A = uuid4()  # rightful owner of NOVEL_ID (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A
FOREIGN_NOVEL_ID = uuid4()  # owned by USER_B (a real novel — just not the caller's)

_OWNERSHIP = {NOVEL_ID: USER_A, FOREIGN_NOVEL_ID: USER_B}

_CHAPTER_ID = uuid4()


def _graph_fixtures() -> tuple[
    list[FakeGraphEntry], list[FakeGraphRelationship], dict[str, set[str]]
]:
    e1 = FakeGraphEntry(id=uuid4(), novel_id=NOVEL_ID, name="Alice")
    e2 = FakeGraphEntry(id=uuid4(), novel_id=NOVEL_ID, name="Bob")
    rel = FakeGraphRelationship(source_id=e1.id, target_id=e2.id)
    adjacency = {str(e1.id): {str(e2.id)}, str(e2.id): {str(e1.id)}}
    return [e1, e2], [rel], adjacency


# ---------------------------------------------------------------------------
# Graph — get_graph + get_shortest_path
# ---------------------------------------------------------------------------


class TestGraphOwnership:
    """Both graph reads gate novel ownership before any data fetch."""

    async def test_owner_get_graph_returns_graph(self) -> None:
        """Matrix case (1): the rightful owner's flow is unchanged."""
        entries, rels, adjacency = _graph_fixtures()
        service, kb_repo, _, novel_repo = make_graph_ownership_service(
            _OWNERSHIP, entries, rels, adjacency
        )

        result = await service.get_graph(novel_id=NOVEL_ID, user_id=USER_A)

        assert len(result.nodes) == 2
        assert len(result.edges) == 1
        # The gate ran with the CALLER's id, then data was fetched.
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]
        assert kb_repo.list_entries_calls == [NOVEL_ID]

    async def test_foreign_novel_get_graph_denied_before_any_fetch(self) -> None:
        """Matrix case (2)+(4): foreign novel → 404 BEFORE entries,
        relationships, or adjacency are read — zero data returned."""
        entries, rels, adjacency = _graph_fixtures()
        service, kb_repo, rel_repo, _ = make_graph_ownership_service(
            _OWNERSHIP, entries, rels, adjacency
        )

        with pytest.raises(NotFoundError, match="Novel"):
            await service.get_graph(novel_id=NOVEL_ID, user_id=USER_B)

        assert kb_repo.list_entries_calls == []
        assert kb_repo.get_by_id_calls == []
        assert rel_repo.list_all_calls == []
        assert rel_repo.adjacency_calls == []

    async def test_unknown_novel_get_graph_indistinguishable(self) -> None:
        """Matrix case (3): unknown novel ≡ foreign novel (anti-enumeration)."""
        entries, rels, adjacency = _graph_fixtures()
        foreign_service, _, _, _ = make_graph_ownership_service(
            _OWNERSHIP, entries, rels, adjacency
        )
        unknown_service, _, _, _ = make_graph_ownership_service(
            _OWNERSHIP, entries, rels, adjacency
        )
        unknown_novel_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await foreign_service.get_graph(novel_id=NOVEL_ID, user_id=USER_B)
        with pytest.raises(NotFoundError) as unknown_exc:
            await unknown_service.get_graph(novel_id=unknown_novel_id, user_id=USER_B)

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Novel ({NOVEL_ID}) not found"
        assert str(unknown_exc.value) == f"Novel ({unknown_novel_id}) not found"

    async def test_owner_get_shortest_path_returns_path(self) -> None:
        """Matrix case (1): the rightful owner's path search is unchanged."""
        entries, rels, adjacency = _graph_fixtures()
        service, _, _, novel_repo = make_graph_ownership_service(
            _OWNERSHIP, entries, rels, adjacency
        )

        result = await service.get_shortest_path(
            novel_id=NOVEL_ID,
            user_id=USER_A,
            source_id=entries[0].id,
            target_id=entries[1].id,
        )

        assert result.path == [entries[0].id, entries[1].id]
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]

    async def test_foreign_novel_get_shortest_path_denied_before_entry_load(
        self,
    ) -> None:
        """Matrix case (2)+(4): foreign novel → 404 BEFORE the source/target
        entry load — foreign entity ids are not enumerable either."""
        entries, rels, adjacency = _graph_fixtures()
        service, kb_repo, _, _ = make_graph_ownership_service(_OWNERSHIP, entries, rels, adjacency)

        with pytest.raises(NotFoundError, match="Novel"):
            await service.get_shortest_path(
                novel_id=NOVEL_ID,
                user_id=USER_B,
                source_id=entries[0].id,
                target_id=entries[1].id,
            )

        assert kb_repo.get_by_id_calls == []


# ---------------------------------------------------------------------------
# KB suggestions — get_suggestions
# ---------------------------------------------------------------------------


class TestSuggestOwnership:
    """``get_suggestions`` gates novel ownership before chapter + KB reads."""

    async def test_owner_get_suggestions_returns_suggestions(self) -> None:
        """Matrix case (1): the rightful owner's flow is unchanged."""
        service, chapter_repo, kb_repo, proactive, novel_repo = make_suggest_ownership_service(
            _OWNERSHIP,
            chapter=FakeSuggestChapter(),
            entries=[FakeGraphEntry(novel_id=NOVEL_ID)],
        )

        result = await service.get_suggestions(
            chapter_id=_CHAPTER_ID,
            novel_id=NOVEL_ID,
            user_id=USER_A,
        )

        assert [s.name for s in result] == ["Aria"]
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]
        assert chapter_repo.get_by_id_calls == [(_CHAPTER_ID, NOVEL_ID)]
        assert proactive.suggest_calls == [NOVEL_ID]
        assert kb_repo.list_entries_calls == [NOVEL_ID]

    async def test_foreign_novel_denied_before_chapter_and_proactive(self) -> None:
        """Matrix case (2)+(4): foreign novel → 404 BEFORE the chapter
        content load, the KB entry load, and the proactive/LLM pipeline."""
        service, chapter_repo, kb_repo, proactive, _ = make_suggest_ownership_service(
            _OWNERSHIP,
            chapter=FakeSuggestChapter(),
            entries=[FakeGraphEntry(novel_id=NOVEL_ID)],
        )

        with pytest.raises(NotFoundError, match="Novel"):
            await service.get_suggestions(
                chapter_id=_CHAPTER_ID,
                novel_id=NOVEL_ID,
                user_id=USER_B,
            )

        assert chapter_repo.get_by_id_calls == []
        assert kb_repo.list_entries_calls == []
        assert proactive.suggest_calls == []

    async def test_unknown_novel_indistinguishable_from_foreign(self) -> None:
        """Matrix case (3): unknown novel ≡ foreign novel."""
        foreign_service, _, _, _, _ = make_suggest_ownership_service(
            _OWNERSHIP, chapter=FakeSuggestChapter()
        )
        unknown_service, _, _, _, _ = make_suggest_ownership_service(
            _OWNERSHIP, chapter=FakeSuggestChapter()
        )
        unknown_novel_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await foreign_service.get_suggestions(
                chapter_id=_CHAPTER_ID, novel_id=NOVEL_ID, user_id=USER_B
            )
        with pytest.raises(NotFoundError) as unknown_exc:
            await unknown_service.get_suggestions(
                chapter_id=_CHAPTER_ID, novel_id=unknown_novel_id, user_id=USER_B
            )

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Novel ({NOVEL_ID}) not found"
        assert str(unknown_exc.value) == f"Novel ({unknown_novel_id}) not found"

    async def test_chapter_not_in_own_novel_denied_before_proactive(self) -> None:
        """S5-style compound: the owner names their own novel but a chapter
        that is not in it → 404 (``NotFoundError``, foreign ≡ unknown),
        before any KB load or LLM call."""
        service, chapter_repo, kb_repo, proactive, _ = make_suggest_ownership_service(
            _OWNERSHIP,
            chapter=None,  # chapter_repo.get_by_id(chapter_id, novel_id) miss
        )

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.get_suggestions(
                chapter_id=_CHAPTER_ID,
                novel_id=NOVEL_ID,
                user_id=USER_A,
            )

        assert chapter_repo.get_by_id_calls == [(_CHAPTER_ID, NOVEL_ID)]
        assert kb_repo.list_entries_calls == []
        assert proactive.suggest_calls == []


# ---------------------------------------------------------------------------
# Consistency — check
# ---------------------------------------------------------------------------


class TestConsistencyOwnership:
    """``check`` gates novel ownership before the cache probe and all phases."""

    async def test_owner_check_returns_report(self) -> None:
        """Matrix case (1): the rightful owner's check is unchanged."""
        service, analyzer, asymmetry, cache, novel_repo = make_consistency_ownership_service(
            _OWNERSHIP
        )
        request = ConsistencyCheckRequest(include_cross_entity=False)

        result = await service.check(
            novel_id=NOVEL_ID,
            request=request,
            user_id=str(USER_A),
        )

        assert result.novel_id == str(NOVEL_ID)
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]
        assert asymmetry.check_calls == [NOVEL_ID]
        assert analyzer.analyze_calls == [NOVEL_ID]
        assert cache.set_calls == [str(NOVEL_ID)]

    async def test_foreign_novel_denied_before_cache_probe_and_phases(self) -> None:
        """Matrix case (2)+(4): foreign novel → 404 BEFORE the cache is
        probed (a cached report must not leak) and before ANY phase —
        algorithmic or LLM — reads the novel's data."""
        service, analyzer, asymmetry, cache, _ = make_consistency_ownership_service(_OWNERSHIP)

        with pytest.raises(NotFoundError, match="Novel"):
            await service.check(
                novel_id=NOVEL_ID,
                request=ConsistencyCheckRequest(),
                user_id=str(USER_B),
            )

        assert cache.hash_calls == 0
        assert cache.get_calls == []
        assert cache.set_calls == []
        assert asymmetry.check_calls == []
        assert analyzer.analyze_calls == []

    async def test_unknown_novel_indistinguishable_from_foreign(self) -> None:
        """Matrix case (3): unknown novel ≡ foreign novel."""
        foreign_service, _, _, cache, _ = make_consistency_ownership_service(_OWNERSHIP)
        unknown_service, _, _, _, _ = make_consistency_ownership_service(_OWNERSHIP)
        unknown_novel_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await foreign_service.check(
                novel_id=NOVEL_ID,
                request=ConsistencyCheckRequest(),
                user_id=str(USER_B),
            )
        with pytest.raises(NotFoundError) as unknown_exc:
            await unknown_service.check(
                novel_id=unknown_novel_id,
                request=ConsistencyCheckRequest(),
                user_id=str(USER_B),
            )

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Novel ({NOVEL_ID}) not found"
        assert str(unknown_exc.value) == f"Novel ({unknown_novel_id}) not found"
        assert cache.get_calls == []
