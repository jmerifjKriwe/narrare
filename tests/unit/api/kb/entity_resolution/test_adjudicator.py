"""Unit tests for the uncertain-band adjudicator (ADR-085 P5, spec §2/D7).

Covers the ``UncertainBandAdjudicator`` adapter over ``KBMergeService``
(Mode-1 governed merge prompt — RULE-02b: no new prompt surface), the
REVIEW-band annotation wiring in the analysis service, and the HTTP
wiring invariants:

- conversion: ``PairCandidate`` → ``MergeRequest`` candidate pairs;
  ``MergeResponse`` decision → ``Adjudication`` verdict (``merge`` ⇒
  supports; every other decision defaults to ``False``);
- failure policy (RULE-11): a failing agent — or a failing merge-service
  factory — is logged and degraded to ``supports_merge=False`` with a
  failure note; the analyze route still returns 200;
- band isolation (spec §8): AUTO_ELIGIBLE and SUPPRESSED pairs never
  reach the adjudicator; the adjudicator runs only when REVIEW pairs
  exist; cache hits serve the stored notes without a re-invocation;
- alias discharge: ``PairCandidate``/``Adjudication`` are real schemas —
  the provisional ``type X = object`` bindings are gone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAliasType

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from narrare.kb.entity_resolution.adjudicator import UncertainBandAdjudicator
from narrare.kb.entity_resolution.contracts import UncertainBandAdjudicatorProtocol
from narrare.kb.entity_resolution.schemas_adjudication import Adjudication, PairCandidate
from narrare.kb.schemas_merge import MergeDecisionResponse, MergeRequest, MergeResponse

from ._adjudicator_helpers import (
    FakeAdjudicator,
    make_analysis_service,
    make_auto_only_corpus_with_distractor,
    make_review_and_auto_corpus,
    review_candidate_for,
)
from ._router_helpers import NOVEL_ID, USER_ID

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from uuid import UUID

    from narrare.kb.merge_contracts import KBMergeServiceProtocol

type MergeServiceFactory = Callable[[UUID, UUID], Awaitable[KBMergeServiceProtocol]]


# --- Fakes ----------------------------------------------------------------------


class _FakeMergeService:
    """Fake ``KBMergeServiceProtocol`` recording requests; canned or raising.

    ``fail_on_name`` simulates a per-pair agent failure (RULE-11
    isolation): only the pair whose first entity name matches raises.
    ``decisions`` overrides the canned single decision (empty list → the
    agent returned no decision row).
    """

    def __init__(
        self,
        *,
        decision: str = "merge",
        confidence: float = 0.9,
        reasoning: str = "same person",
        decisions: list[MergeDecisionResponse] | None = None,
        fail_on_name: str | None = None,
    ) -> None:
        self.calls: list[tuple[UUID, UUID, MergeRequest]] = []
        self._decision = decision
        self._confidence = confidence
        self._reasoning = reasoning
        self._decisions = decisions
        self._fail_on_name = fail_on_name

    async def analyze_merge_candidates(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: MergeRequest,
    ) -> MergeResponse:
        self.calls.append((novel_id, user_id, request))
        first = (request.candidate_pairs or [{}])[0].get("entity_1")
        if self._fail_on_name is not None and first == self._fail_on_name:
            raise RuntimeError("boom")
        decisions = self._decisions
        if decisions is None:
            decisions = [
                MergeDecisionResponse(
                    pair_id="1",
                    decision=self._decision,
                    confidence=self._confidence,
                    reasoning=self._reasoning,
                )
            ]
        return MergeResponse(merge_decisions=decisions, overall_notes="")


def _factory_for(
    service: _FakeMergeService,
    received: list[tuple[UUID, UUID]] | None = None,
    *,
    error: Exception | None = None,
) -> MergeServiceFactory:
    """Async factory handing out ``service`` (or raising), recording calls."""

    async def factory(novel_id: UUID, user_id: UUID) -> KBMergeServiceProtocol:
        if received is not None:
            received.append((novel_id, user_id))
        if error is not None:
            raise error
        return service

    return factory


def _candidate(
    key: str = "pair1",
    name_a: str = "Anna",
    name_b: str = "Anna Meyer",
    entity_type: str = "character",
) -> PairCandidate:
    return PairCandidate(pair_key=key, entity_type=entity_type, name_a=name_a, name_b=name_b)


def _adjudicator(
    service: _FakeMergeService,
    received: list[tuple[UUID, UUID]] | None = None,
    *,
    factory_error: Exception | None = None,
) -> UncertainBandAdjudicator:
    factory = _factory_for(service, received, error=factory_error)
    return UncertainBandAdjudicator(merge_service_factory=factory)


# --- Adapter: conversion + verdict mapping ----------------------------------------


class TestAdjudicateConversion:
    async def test_merge_decision_converts_pair_and_supports_merge(self) -> None:
        received: list[tuple[UUID, UUID]] = []
        service = _FakeMergeService(decision="merge", confidence=0.9, reasoning="same person")
        adjudicator = _adjudicator(service, received)

        (result,) = await adjudicator.adjudicate(NOVEL_ID, USER_ID, [_candidate(key="k1")])

        assert isinstance(result, Adjudication)
        assert result.pair_key == "k1"
        assert result.supports_merge is True
        assert "merge" in result.note
        assert "same person" in result.note
        # The governed merge service received the converted runtime data.
        novel_id, user_id, request = service.calls[0]
        assert (novel_id, user_id) == (NOVEL_ID, USER_ID)
        assert request.entity_type == "character"
        assert request.candidate_pairs == [{"entity_1": "Anna", "entity_2": "Anna Meyer"}]
        # The merge service was resolved through the injected factory.
        assert received == [(NOVEL_ID, USER_ID)]

    @pytest.mark.parametrize(
        ("decision", "supported"), [("distinct", False), ("uncertain", False), ("", False)]
    )
    async def test_non_merge_decisions_default_to_not_supported(
        self, decision: str, supported: bool
    ) -> None:
        service = _FakeMergeService(decision=decision)
        (result,) = await _adjudicator(service).adjudicate(NOVEL_ID, USER_ID, [_candidate()])

        assert result.supports_merge is supported

    async def test_adjudicator_satisfies_protocol(self) -> None:
        assert isinstance(_adjudicator(_FakeMergeService()), UncertainBandAdjudicatorProtocol)


# --- Adapter: failure policy (RULE-11 — degrade, never crash) ---------------------


class TestAdjudicateFailurePolicy:
    async def test_agent_failure_is_logged_and_degraded_to_false_with_note(self) -> None:
        service = _FakeMergeService(fail_on_name="Anna")

        with capture_logs() as logs:
            (result,) = await _adjudicator(service).adjudicate(
                NOVEL_ID, USER_ID, [_candidate(key="k9")]
            )

        assert result.pair_key == "k9"
        assert result.supports_merge is False
        assert "boom" in result.note
        failure = [e for e in logs if e["event"] == "resolution_adjudication_failed"]
        assert len(failure) == 1
        assert failure[0]["pair_key"] == "k9"
        assert failure[0]["novel_id"] == str(NOVEL_ID)

    async def test_empty_decisions_are_logged_and_degraded_to_false(self) -> None:
        service = _FakeMergeService(decisions=[])

        with capture_logs() as logs:
            (result,) = await _adjudicator(service).adjudicate(NOVEL_ID, USER_ID, [_candidate()])

        assert result.supports_merge is False
        assert result.note != ""
        assert [e for e in logs if e["event"] == "resolution_adjudication_empty"]

    async def test_one_pair_failure_does_not_poison_the_others(self) -> None:
        service = _FakeMergeService(decision="merge", fail_on_name="Bella")
        pairs = [_candidate(key="ok", name_a="Anna"), _candidate(key="bad", name_a="Bella")]

        results = await _adjudicator(service).adjudicate(NOVEL_ID, USER_ID, pairs)

        by_key = {r.pair_key: r for r in results}
        assert by_key["ok"].supports_merge is True
        assert by_key["bad"].supports_merge is False
        assert len(service.calls) == 2

    async def test_failing_factory_degrades_every_pair(self) -> None:
        service = _FakeMergeService()
        adjudicator = _adjudicator(service, factory_error=RuntimeError("no model"))

        with capture_logs() as logs:
            results = await adjudicator.adjudicate(
                NOVEL_ID, USER_ID, [_candidate(key="a"), _candidate(key="b")]
            )

        assert all(r.supports_merge is False for r in results)
        assert all("no model" in r.note for r in results)
        assert service.calls == []  # never reached
        assert [e for e in logs if e["event"] == "resolution_adjudication_failed"]

    async def test_empty_pair_list_skips_the_factory(self) -> None:
        received: list[tuple[UUID, UUID]] = []
        service = _FakeMergeService()
        adjudicator = _adjudicator(service, received)

        result = await adjudicator.adjudicate(NOVEL_ID, USER_ID, [])

        assert result == []
        assert received == []  # inert by default — no merge service built
        assert service.calls == []


# --- Analysis-service wiring: REVIEW band only, cache-friendly ---------------------


class TestReviewBandWiring:
    async def test_analyze_annotates_review_suggestions_and_skips_auto_band(self) -> None:
        snapshots, review_id = make_review_and_auto_corpus()
        fake_adjudicator = FakeAdjudicator(note="LLM: likely the same person.")
        service = make_analysis_service(snapshots, fake_adjudicator)

        response = await service.analyze(NOVEL_ID, USER_ID)

        by_band = {s.band: s for s in response.suggestions}
        assert by_band["REVIEW"].adjudication_note == "LLM: likely the same person."
        assert by_band["AUTO_ELIGIBLE"].adjudication_note is None
        # Exactly the REVIEW pair was submitted, keyed by its suggestion id.
        assert fake_adjudicator.calls == [(NOVEL_ID, USER_ID, [review_candidate_for(snapshots)])]
        assert fake_adjudicator.calls[0][2][0].pair_key == review_id

    async def test_analyze_without_review_pairs_never_calls_the_adjudicator(self) -> None:
        snapshots = make_auto_only_corpus_with_distractor()
        fake_adjudicator = FakeAdjudicator()
        service = make_analysis_service(snapshots, fake_adjudicator)

        response = await service.analyze(NOVEL_ID, USER_ID)

        assert response.stats.auto_eligible == 1
        assert response.stats.suppressed == 1
        assert fake_adjudicator.calls == []  # spec §8: deterministic bands stay LLM-free

    async def test_analyze_without_adjudicator_keeps_notes_none(self) -> None:
        snapshots, _ = make_review_and_auto_corpus()
        service = make_analysis_service(snapshots)

        response = await service.analyze(NOVEL_ID, USER_ID)

        assert all(s.adjudication_note is None for s in response.suggestions)

    async def test_cache_hit_serves_stored_notes_without_re_invoking(self) -> None:
        snapshots, _ = make_review_and_auto_corpus()
        fake_adjudicator = FakeAdjudicator(note="cached note")
        service = make_analysis_service(snapshots, fake_adjudicator)

        first = await service.analyze(NOVEL_ID, USER_ID)
        second = await service.analyze(NOVEL_ID, USER_ID)

        assert first.cache_hit is False
        assert second.cache_hit is True
        assert fake_adjudicator.calls_count == 1  # LLM ran once, on the miss
        assert second.suggestions[0].adjudication_note == "cached note"


# --- Alias discharge (binding note 1) ----------------------------------------------


class TestAliasDischarge:
    def test_provisional_aliases_resolve_to_real_schemas(self) -> None:
        """The last two ``type X = object`` bindings now name real schemas.

        PEP 695 aliases resolve lazily (``TypeAliasType.__value__``); the
        helper tolerates a future direct-class assignment.
        """
        from narrare.kb.entity_resolution import contracts

        def _resolved(alias: object) -> object:
            if isinstance(alias, TypeAliasType):
                return alias.__value__
            return alias

        assert _resolved(contracts.PairCandidate) is PairCandidate
        assert _resolved(contracts.Adjudication) is Adjudication


# --- HTTP surface wiring -------------------------------------------------------------


class TestHttpWiring:
    def test_analyze_route_declares_ai_analysis_limiter_and_others_stay_llm_free(self) -> None:
        """The adjudicated analyze path carries AI_ANALYSIS_LIMITER (T8
        carry-forward); endorse/suggestions/reject stay deterministic."""
        from fastapi.routing import APIRoute

        from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
        from narrare.kb.entity_resolution.router import router

        limiterd: dict[str, bool] = {}
        for route in router.routes:
            if not isinstance(route, APIRoute) or "/kb/resolution/" not in route.path:
                continue
            name = route.path.rsplit("/", 1)[-1]
            limiterd[name] = AI_ANALYSIS_LIMITER in [d.dependency for d in route.dependencies]

        # Only the adjudicated analyze path is LLM-calling; the deterministic
        # surface (cache reads, endorse re-validation, reject) stays limiter-free.
        assert limiterd == {
            "analyze": True,
            "suggestions": False,
            "endorse": False,
            "reject": False,
        }

    def test_analyze_route_survives_failing_merge_agent_with_200(self) -> None:
        """RULE-11 end to end: agent failure → note, never a crashed analyze."""
        from narrare._app.dependencies_auth import get_current_user_id
        from narrare.kb.entity_resolution.dependencies import (
            get_adjudicated_analyzer,
            get_novel_scope_repository,
        )
        from narrare.kb.entity_resolution.router import router as resolution_router
        from tests.factories import make_novel
        from tests.fakes.fake_novel_repo import FakeNovelRepository

        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=NOVEL_ID, user_id=USER_ID))
        snapshots, _ = make_review_and_auto_corpus()
        adjudicator = UncertainBandAdjudicator(
            merge_service_factory=_factory_for(
                _FakeMergeService(), error=RuntimeError("no model config")
            )
        )
        service = make_analysis_service(snapshots, adjudicator)

        app = FastAPI()
        app.include_router(resolution_router, prefix="/api/v1")
        app.dependency_overrides[get_current_user_id] = lambda: str(USER_ID)
        app.dependency_overrides[get_novel_scope_repository] = lambda: novel_repo
        app.dependency_overrides[get_adjudicated_analyzer] = lambda: service

        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/novels/{NOVEL_ID}/kb/resolution/analyze",
                json={"refresh": False},
            )

        assert response.status_code == 200  # RULE-11: analysis never crashes
        suggestions = response.json()["suggestions"]
        review = next(s for s in suggestions if s["band"] == "REVIEW")
        assert "unavailable" in review["adjudication_note"]
        auto = next(s for s in suggestions if s["band"] == "AUTO_ELIGIBLE")
        assert auto["adjudication_note"] is None
