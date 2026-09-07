"""Unit tests for the resolution endorse/reject service (ADR-085 P4, spec §7).

Service-level pins that are awkward to arrange through the HTTP seam:

- re-validation calls ``analyze(refresh=True)`` — a fresh scoring pass,
  never a cache read (binding note: stateless revalidation);
- the re-scored pair confidence is carried into the ``MergePlan``;
- the ``survivor_id`` override must name one of the suggested pair
  (foreign UUIDs are a degenerate plan → ValidationError → 422);
- executor ``ValueError`` → ``ValidationError`` (binding note: 422 at the
  HTTP seam), ``NotFoundError`` propagates (→ 404 via the global handler);
- the automatic survivor pick passes the pair in ``(min_id, max_id)``
  order to :func:`select_survivor` — a total rank tie resolves to the
  min id, proving caller-independent ordering;
- a successful merge invalidates the analysis cache;
- ``reject`` persists the dismissal via the injected store and logs the
  acting user (RULE-11 audit).

Also pins the :class:`ResolutionDismissalStore` adapter: the reserved
``resolution:`` fingerprint namespace is added on write and stripped on
read, keeping consistency findings and resolution rejections disjoint.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from structlog.testing import capture_logs

from narrare.kb.entity_resolution._dismissal_store import ResolutionDismissalStore
from narrare.kb.entity_resolution.endorse_service import ResolutionEndorseService
from narrare.kb.entity_resolution.schemas_resolution import (
    BandStats,
    MergeExecutionResult,
    MergePlan,
    ResolutionAnalysisResponse,
    SuggestionResponse,
)
from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError

from ._endorse_helpers import FakeDismissedStore, suggestion_id_for

NOVEL = uuid4()
USER = uuid4()


# --- Fakes ----------------------------------------------------------------------


class _FakeAnalyzer:
    """Canned ResolutionAnalysisService double recording call shapes."""

    def __init__(self, response: ResolutionAnalysisResponse) -> None:
        self.response = response
        self.analyze_calls: list[tuple[UUID, UUID, bool]] = []
        self.invalidated: list[UUID] = []

    async def analyze(
        self, novel_id: UUID, user_id: UUID, *, refresh: bool = False
    ) -> ResolutionAnalysisResponse:
        self.analyze_calls.append((novel_id, user_id, refresh))
        return self.response

    async def invalidate(self, novel_id: UUID) -> None:
        self.invalidated.append(novel_id)


class _FakeExecutor:
    """Records the plan it receives; optionally raises like the real one."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.plans: list[MergePlan] = []
        self._error = error

    async def execute(self, novel_id: UUID, user_id: UUID, plan: MergePlan) -> MergeExecutionResult:
        if self._error is not None:
            raise self._error
        self.plans.append(plan)
        return MergeExecutionResult(
            survivor_id=plan.survivor_id,
            loser_id=plan.loser_id,
            merged_fact_keys=[],
            repointed_relationships=0,
            skipped_relationships=0,
            conflicts=[],
        )


class _FakeEntry:
    def __init__(self, entry_id: UUID, *, name: str = "Anna") -> None:
        self.id = entry_id
        self.novel_id = NOVEL
        self.name = name
        self.metadata_: dict[str, object] = {}
        self.created_at = datetime.now(tz=UTC)


class _FakeKbRepo:
    def __init__(self, entries: list[_FakeEntry]) -> None:
        self._entries = {e.id: e for e in entries}

    async def get_by_id(self, entry_id: UUID) -> _FakeEntry | None:
        return self._entries.get(entry_id)


class _FakeRelRepo:
    def __init__(self, counts: dict[UUID, int] | None = None) -> None:
        self._counts = counts or {}

    async def list_for_entry(self, entry_id: UUID, direction: str | None = None) -> list[object]:
        return [None] * self._counts.get(entry_id, 0)


# --- Helpers --------------------------------------------------------------------


def _suggestion(a: UUID, b: UUID, *, confidence: float = 0.645) -> ResolutionAnalysisResponse:
    return ResolutionAnalysisResponse(
        suggestions=[
            SuggestionResponse(
                suggestion_id=suggestion_id_for(a, b),
                entry_a_id=min(a, b),
                entry_b_id=max(a, b),
                name_a="Anna",
                name_b="Anna Meyer",
                confidence=confidence,
                band="REVIEW",
                auto_merge_eligible=False,
                signals=[],
            )
        ],
        stats=BandStats(review=1, auto_eligible=0, suppressed=0),
        cache_hit=False,
    )


def _service(
    response: ResolutionAnalysisResponse,
    executor: _FakeExecutor | None = None,
    kb_repo: _FakeKbRepo | None = None,
    rel_repo: _FakeRelRepo | None = None,
    store: FakeDismissedStore | None = None,
) -> tuple[ResolutionEndorseService, _FakeAnalyzer, _FakeExecutor, FakeDismissedStore]:
    analyzer = _FakeAnalyzer(response)
    fake_executor = executor if executor is not None else _FakeExecutor()
    if kb_repo is None:
        # Seed the suggested pair so the auto-survivor path can load them.
        (suggestion,) = response.suggestions
        kb_repo = _FakeKbRepo(
            [
                _FakeEntry(suggestion.entry_a_id, name=suggestion.name_a),
                _FakeEntry(suggestion.entry_b_id, name=suggestion.name_b),
            ]
        )
    fake_rel = rel_repo if rel_repo is not None else _FakeRelRepo()
    fake_store = store if store is not None else FakeDismissedStore()
    service = ResolutionEndorseService(
        analyzer=cast("object", analyzer),
        executor=cast("object", fake_executor),
        kb_repo=cast("object", kb_repo),
        rel_repo=cast("object", fake_rel),
        dismissals=fake_store,
    )
    return service, analyzer, fake_executor, fake_store


# --- Endorse --------------------------------------------------------------------


class TestEndorse:
    async def test_endorse_rescores_fresh_and_supplies_confidence(self) -> None:
        """Re-validation is a refresh=True scoring pass; confidence travels."""
        a, b = uuid4(), uuid4()
        service, analyzer, executor, _ = _service(_suggestion(a, b, confidence=0.61))

        await service.endorse(NOVEL, USER, suggestion_id_for(a, b))

        assert analyzer.analyze_calls == [(NOVEL, USER, True)]
        (plan,) = executor.plans
        assert plan.confidence == pytest.approx(0.61)
        assert plan.suggestion_id == suggestion_id_for(a, b)
        # "Anna Meyer" (the longer name) wins the §6.1 rank → min id loses.
        assert plan.survivor_id == max(a, b)
        assert plan.loser_id == min(a, b)

    async def test_endorse_invalidates_analysis_cache_on_success(self) -> None:
        a, b = uuid4(), uuid4()
        service, analyzer, _, _ = _service(_suggestion(a, b))

        await service.endorse(NOVEL, USER, suggestion_id_for(a, b))

        assert analyzer.invalidated == [NOVEL]

    async def test_endorse_unknown_or_low_band_returns_conflict(self) -> None:
        """An id missing from the fresh re-score (stale/rejected/suppressed)."""
        a, b = uuid4(), uuid4()
        service, _, executor, _ = _service(_suggestion(a, b))

        with pytest.raises(ConflictError):
            await service.endorse(NOVEL, USER, "deadbeefdeadbeef")

        assert executor.plans == []


class TestEndorseOverride:
    async def test_override_not_in_pair_is_validation_error(self) -> None:
        a, b = uuid4(), uuid4()
        service, _, executor, _ = _service(_suggestion(a, b))

        with pytest.raises(ValidationError):
            await service.endorse(NOVEL, USER, suggestion_id_for(a, b), survivor_id=uuid4())

        assert executor.plans == []

    async def test_executor_value_error_maps_to_validation_error(self) -> None:
        a, b = uuid4(), uuid4()
        executor = _FakeExecutor(error=ValueError("survivor is deprecated — stale plan"))
        service, _, _, _ = _service(_suggestion(a, b), executor=executor)

        with pytest.raises(ValidationError):
            await service.endorse(NOVEL, USER, suggestion_id_for(a, b))

    async def test_executor_not_found_error_propagates(self) -> None:
        a, b = uuid4(), uuid4()
        executor = _FakeExecutor(error=NotFoundError("KBEntry", identifier=str(a)))
        service, _, _, _ = _service(_suggestion(a, b), executor=executor)

        with pytest.raises(NotFoundError):
            await service.endorse(NOVEL, USER, suggestion_id_for(a, b))

    async def test_explicit_override_names_the_loser(self) -> None:
        a, b = uuid4(), uuid4()
        service, _, executor, _ = _service(_suggestion(a, b))

        result = await service.endorse(NOVEL, USER, suggestion_id_for(a, b), survivor_id=b)

        assert result.survivor_id == b
        (plan,) = executor.plans
        assert plan.loser_id == a


class TestAutoSurvivor:
    async def test_rank_tie_resolves_to_min_id_pair_ordering(self) -> None:
        """Equal ranks → select_survivor's first argument (min id) wins."""
        a, b = sorted((uuid4(), uuid4()))
        entries = [_FakeEntry(a, name="Anna X"), _FakeEntry(b, name="Anna Y")]
        fixed = datetime.now(tz=UTC)
        for entry in entries:
            entry.created_at = fixed
        service, _, executor, _ = _service(
            _suggestion(a, b),
            kb_repo=_FakeKbRepo(entries),
            rel_repo=_FakeRelRepo(),  # equal (zero) edge counts
        )

        await service.endorse(NOVEL, USER, suggestion_id_for(a, b))

        (plan,) = executor.plans
        assert plan.survivor_id == a  # the tie falls to the (min, max) order
        assert plan.loser_id == b


# --- Reject ---------------------------------------------------------------------


class TestReject:
    async def test_reject_persists_dismissal_and_logs_user(self) -> None:
        a, b = uuid4(), uuid4()
        service, analyzer, _, store = _service(_suggestion(a, b))
        pair_id = suggestion_id_for(a, b)

        with capture_logs() as logs:
            await service.reject(NOVEL, USER, pair_id)

        assert store.dismiss_calls == [(NOVEL, pair_id)]
        assert analyzer.invalidated == []  # the analysis cache stays
        logged = [e for e in logs if e["event"] == "resolution_suggestion_rejected"]
        assert logged and logged[0]["user_id"] == str(USER)


# --- Dismissal store adapter ------------------------------------------------------


class _FakeFindingRepo:
    """DismissedFindingRepository double capturing fingerprint writes."""

    def __init__(self) -> None:
        self.rows: list[tuple[UUID, str]] = []
        self.reads: list[UUID] = []

    async def dismiss(self, novel_id: UUID, fingerprint: str, reason: str | None = None) -> None:
        self.rows.append((novel_id, fingerprint))

    async def list_dismissed(self, novel_id: UUID) -> list[str]:
        self.reads.append(novel_id)
        return ["resolution:abc123", "some description::Anna, Bo", "resolution:def456"]


class TestResolutionDismissalStore:
    async def test_dismiss_namespaces_the_fingerprint(self) -> None:
        repo = _FakeFindingRepo()
        store = ResolutionDismissalStore(cast("object", repo))

        await store.dismiss(NOVEL, "abc123")

        assert repo.rows == [(NOVEL, "resolution:abc123")]

    async def test_rejected_ids_strip_prefix_and_ignore_other_domains(self) -> None:
        repo = _FakeFindingRepo()
        store = ResolutionDismissalStore(cast("object", repo))

        rejected = await store.rejected_ids(NOVEL)

        assert rejected == frozenset({"abc123", "def456"})
