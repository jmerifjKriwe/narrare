"""S8 — IDOR regression tests: ownership gates on KB improve + worldbuilding (service).

Before the S8 fix, ``KBImproveService.analyze/apply`` and
``WorldbuildingService.analyze/apply_connections`` resolved access by bare
``novel_id``/``entry_id``: a foreign body received LLM improvement
suggestions for another user's entry, and ``apply`` wrote the foreign
entry (field updates + relationships). The worldbuilding ``apply`` even
carried a ``user_id`` parameter it never used.

The fix (plan S8, Pattern B) is a service-entry gate
``novel_repo.get_by_id(novel_id, user_id)`` → ``NotFoundError`` BEFORE any
cache lookup, analyzer/LLM call, entry load, or write — plus an
entry∈novel assertion on the improve paths (a foreign entry under an
owned novel is indistinguishable from an unknown one). Foreign ≡ unknown
(anti-enumeration): both raise ``NotFoundError`` → 404.

The HTTP-level matrix (all 4 endpoints) lives in
``test_improve_worldbuilding_ownership_api.py`` (RULE-04 split); the
entry∈novel matrix for worldbuilding apply (W2) lives in
``test_worldbuilding_apply_entry_ownership.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare.kb.worldbuilding_contracts import (
    WorldbuildingAnalysisRequest,
    WorldbuildingApplyRequest,
)
from narrare_core.shared.errors import NotFoundError

from ._test_fakes_improve_worldbuilding import (
    CountingImproveAnalyzer,
    FakeKBEntry,
    RecordingKBRepo,
    RecordingRelationshipRepo,
    make_improve_analysis,
    make_improve_ownership_service,
    make_worldbuilding_analysis,
    make_worldbuilding_ownership_service,
)

if TYPE_CHECKING:
    from narrare.kb.improve_service import KBImproveService

    from ._test_fakes import FakeNovelRepo

USER_A = uuid4()  # rightful owner of NOVEL_ID and its entry (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A
FOREIGN_NOVEL_ID = uuid4()  # owned by USER_B (a real novel — just not the caller's)

ENTRY_ID = uuid4()  # USER_A's entry inside NOVEL_ID
FOREIGN_ENTRY_ID = uuid4()  # USER_B's entry inside FOREIGN_NOVEL_ID

_OWNERSHIP = {NOVEL_ID: USER_A, FOREIGN_NOVEL_ID: USER_B}


def _improve_service() -> tuple[
    KBImproveService,
    CountingImproveAnalyzer,
    RecordingKBRepo,
    RecordingRelationshipRepo,
    FakeNovelRepo,
]:
    """Improve service over the victim's entry + real ownership map."""
    entries = {
        ENTRY_ID: FakeKBEntry(id=ENTRY_ID, novel_id=NOVEL_ID, metadata_={"age": 30}),
        FOREIGN_ENTRY_ID: FakeKBEntry(id=FOREIGN_ENTRY_ID, novel_id=FOREIGN_NOVEL_ID),
    }
    return make_improve_ownership_service(_OWNERSHIP, entries)


# ---------------------------------------------------------------------------
# KB improve — analyze
# ---------------------------------------------------------------------------


class TestImproveAnalyzeOwnership:
    """``analyze`` gates novel + entry ownership before any analyzer work."""

    async def test_owner_analyze_runs_analyzer(self) -> None:
        """Matrix case (1): the rightful owner's flow is unchanged."""
        service, analyzer, _, _, novel_repo = _improve_service()

        result = await service.analyze(novel_id=NOVEL_ID, entry_id=ENTRY_ID, user_id=USER_A)

        assert len(result.suggestions) == len(make_improve_analysis().suggestions)
        assert analyzer.analyze_calls == [(NOVEL_ID, ENTRY_ID)]
        # The gate ran with the CALLER's id.
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]

    async def test_foreign_novel_denied_before_any_work(self) -> None:
        """Matrix case (2)+(4): foreign novel → 404 BEFORE entry load, cache, or LLM."""
        service, analyzer, kb_repo, _, _ = _improve_service()

        with pytest.raises(NotFoundError, match="Novel"):
            await service.analyze(novel_id=NOVEL_ID, entry_id=ENTRY_ID, user_id=USER_B)

        assert analyzer.analyze_calls == []
        assert kb_repo.get_by_id_calls == []

    async def test_unknown_novel_indistinguishable_from_foreign(self) -> None:
        """Matrix case (3): unknown novel ≡ foreign novel (anti-enumeration)."""
        foreign_service, _, _, _, _ = _improve_service()
        unknown_service, _, _, _, _ = _improve_service()
        unknown_novel_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await foreign_service.analyze(novel_id=NOVEL_ID, entry_id=ENTRY_ID, user_id=USER_B)
        with pytest.raises(NotFoundError) as unknown_exc:
            await unknown_service.analyze(
                novel_id=unknown_novel_id, entry_id=ENTRY_ID, user_id=USER_B
            )

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Novel ({NOVEL_ID}) not found"
        assert str(unknown_exc.value) == f"Novel ({unknown_novel_id}) not found"

    async def test_foreign_entry_under_own_novel_denied_before_analyzer(self) -> None:
        """Entry∈novel: USER_A names their own novel but a foreign entry → 404
        BEFORE any analyzer/LLM call (the entry body never reaches the LLM)."""
        service, analyzer, kb_repo, _, _ = _improve_service()

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.analyze(novel_id=NOVEL_ID, entry_id=FOREIGN_ENTRY_ID, user_id=USER_A)

        assert analyzer.analyze_calls == []
        assert kb_repo.get_by_id_calls == [FOREIGN_ENTRY_ID]

    async def test_unknown_entry_indistinguishable_from_foreign(self) -> None:
        """Unknown entry ≡ foreign entry under the caller's own novel."""
        service, analyzer, _, _, _ = _improve_service()
        unknown_entry_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await service.analyze(novel_id=NOVEL_ID, entry_id=FOREIGN_ENTRY_ID, user_id=USER_A)
        with pytest.raises(NotFoundError) as unknown_exc:
            await service.analyze(novel_id=NOVEL_ID, entry_id=unknown_entry_id, user_id=USER_A)

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"KBEntry ({FOREIGN_ENTRY_ID}) not found"
        assert str(unknown_exc.value) == f"KBEntry ({unknown_entry_id}) not found"
        assert analyzer.analyze_calls == []


# ---------------------------------------------------------------------------
# KB improve — apply
# ---------------------------------------------------------------------------


class TestImproveApplyOwnership:
    """``apply`` gates novel + entry ownership before cache, analyzer, writes."""

    async def test_owner_apply_applies_and_invalidates_cache(self) -> None:
        """Matrix case (1): owner applies from the cached analysis (no LLM)."""
        service, analyzer, kb_repo, rel_repo, _ = _improve_service()

        result = await service.apply(
            novel_id=NOVEL_ID,
            entry_id=ENTRY_ID,
            suggestion_ids=[0, 1],
            user_id=USER_A,
        )

        assert result.success is True
        assert result.applied_count == 2
        # Cache hit — the analyzer/LLM never ran.
        assert analyzer.cached_calls == [ENTRY_ID]
        assert analyzer.analyze_calls == []
        # Field update + one connect relationship + cache invalidation.
        assert len(kb_repo.update_calls) == 1
        assert len(rel_repo.created) == 1
        assert analyzer.invalidate_calls == [ENTRY_ID]

    async def test_foreign_novel_denied_before_cache_lookup(self) -> None:
        """Matrix case (2)+(4): gate runs BEFORE the ``get_cached_analysis``
        cache lookup too (plan S8 hazard) — no cache probe, no LLM, no write."""
        service, analyzer, kb_repo, rel_repo, _ = _improve_service()

        with pytest.raises(NotFoundError, match="Novel"):
            await service.apply(
                novel_id=NOVEL_ID,
                entry_id=ENTRY_ID,
                suggestion_ids=[0],
                user_id=USER_B,
            )

        assert analyzer.cached_calls == []
        assert analyzer.analyze_calls == []
        assert kb_repo.update_calls == []
        assert rel_repo.created == []
        assert analyzer.invalidate_calls == []

    async def test_foreign_entry_under_own_novel_denied_no_writes(self) -> None:
        """Foreign entry under an owned novel → 404, apply writes nothing."""
        service, analyzer, kb_repo, rel_repo, _ = _improve_service()

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.apply(
                novel_id=NOVEL_ID,
                entry_id=FOREIGN_ENTRY_ID,
                suggestion_ids=[0],
                user_id=USER_A,
            )

        assert analyzer.cached_calls == []
        assert kb_repo.update_calls == []
        assert rel_repo.created == []
        assert analyzer.invalidate_calls == []

    async def test_unknown_entry_indistinguishable_from_foreign(self) -> None:
        """Unknown entry ≡ foreign entry — identical error shape."""
        service, _, _, _, _ = _improve_service()
        unknown_entry_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await service.apply(
                novel_id=NOVEL_ID,
                entry_id=FOREIGN_ENTRY_ID,
                suggestion_ids=[0],
                user_id=USER_A,
            )
        with pytest.raises(NotFoundError) as unknown_exc:
            await service.apply(
                novel_id=NOVEL_ID,
                entry_id=unknown_entry_id,
                suggestion_ids=[0],
                user_id=USER_A,
            )

        assert str(foreign_exc.value) == f"KBEntry ({FOREIGN_ENTRY_ID}) not found"
        assert str(unknown_exc.value) == f"KBEntry ({unknown_entry_id}) not found"


# ---------------------------------------------------------------------------
# Worldbuilding — analyze + apply_connections
# ---------------------------------------------------------------------------


class TestWorldbuildingOwnership:
    """Both worldbuilding verbs gate novel ownership at service entry."""

    async def test_owner_analyze_runs_analyzer(self) -> None:
        """Matrix case (1): the rightful owner's analyze flow is unchanged."""
        service, analyzer, _, _, _, novel_repo = make_worldbuilding_ownership_service(_OWNERSHIP)

        result = await service.analyze(
            novel_id=NOVEL_ID,
            request=WorldbuildingAnalysisRequest(),
            user_id=USER_A,
        )

        assert result.novel_id == str(NOVEL_ID)
        assert analyzer.analyze_calls == [NOVEL_ID]
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]

    async def test_owner_apply_creates_relationships(self) -> None:
        """Matrix case (1): owner's apply creates relationships + invalidates."""
        service, _, rel_repo, cache, _, _ = make_worldbuilding_ownership_service(_OWNERSHIP)
        analysis = make_worldbuilding_analysis(NOVEL_ID)

        result = await service.apply_connections(
            novel_id=NOVEL_ID,
            user_id=USER_A,
            request=WorldbuildingApplyRequest(finding_indices=[0]),
            analysis=analysis,
        )

        assert result.success is True
        assert result.created_count == 1
        assert len(rel_repo.created) == 1
        assert cache.delete_all_calls == [str(NOVEL_ID)]

    async def test_foreign_novel_denied_before_analyzer(self) -> None:
        """Matrix case (2): foreign novel on analyze → 404, zero LLM calls."""
        service, analyzer, _, _, _, _ = make_worldbuilding_ownership_service(_OWNERSHIP)

        with pytest.raises(NotFoundError, match="Novel"):
            await service.analyze(
                novel_id=NOVEL_ID,
                request=WorldbuildingAnalysisRequest(),
                user_id=USER_B,
            )

        assert analyzer.analyze_calls == []

    async def test_foreign_novel_denied_on_apply_zero_effects(self) -> None:
        """Matrix case (2)+(4): foreign novel on apply → 404, zero writes —
        the previously unused ``user_id`` param is now the gate input."""
        service, _, rel_repo, cache, _, _ = make_worldbuilding_ownership_service(_OWNERSHIP)
        analysis = make_worldbuilding_analysis(NOVEL_ID)

        with pytest.raises(NotFoundError, match="Novel"):
            await service.apply_connections(
                novel_id=NOVEL_ID,
                user_id=USER_B,
                request=WorldbuildingApplyRequest(finding_indices=[0]),
                analysis=analysis,
            )

        assert rel_repo.exists_calls == []
        assert rel_repo.created == []
        assert cache.delete_all_calls == []

    async def test_unknown_novel_indistinguishable_from_foreign(self) -> None:
        """Matrix case (3): unknown ≡ foreign on both verbs."""
        service, analyzer, _, _, _, _ = make_worldbuilding_ownership_service(_OWNERSHIP)
        unknown_novel_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await service.analyze(
                novel_id=NOVEL_ID,
                request=WorldbuildingAnalysisRequest(),
                user_id=USER_B,
            )
        with pytest.raises(NotFoundError) as unknown_exc:
            await service.analyze(
                novel_id=unknown_novel_id,
                request=WorldbuildingAnalysisRequest(),
                user_id=USER_B,
            )

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Novel ({NOVEL_ID}) not found"
        assert str(unknown_exc.value) == f"Novel ({unknown_novel_id}) not found"
        assert analyzer.analyze_calls == []
