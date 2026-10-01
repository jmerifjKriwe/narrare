"""Unit tests for evals/rerank_pilot.py (Task 16, ADR-090) — dry-run only.

The pilot's real mode needs the ~600 MB LateOn checkpoint; CI (and these
tests) exercise the measurement logic through the deterministic dry-run
scorer and the pure helpers instead (same pattern as
``tests/unit/core/embeddings/test_rerank.py``: no checkpoint download).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from evals.rerank_pilot import (
    RECALL_K,
    CaseResult,
    OrderMetrics,
    classify_verdict,
    rerank_arm,
    run_pilot,
    summarize,
    try_real_reranker,
)
from evals.rerank_pilot_substrate import (
    Block,
    build_pool,
    case_blocks,
    lexical_surrogate,
    load_cases,
    seeded_scores,
    to_candidate,
)

from narrare_core.embeddings import RerankCandidate

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _candidate(text: str, base_score: float) -> RerankCandidate:
    return RerankCandidate(
        source_id=uuid4(), source_type="kb_entry", text=text, base_score=base_score
    )


def _case_result(
    reciprocal_baseline: float, reciprocal_rerank: float, *, language: str = "en"
) -> CaseResult:
    def metrics(rr: float) -> OrderMetrics:
        rank = round(1 / rr) if rr else 0
        return OrderMetrics(
            gold_ranks=(rank,) if rank else (),
            best_gold_rank=rank,
            reciprocal_rank=rr,
            recall_at_3=1.0 if rank and rank <= RECALL_K else 0.0,
        )

    return CaseResult(
        name="case",
        language=language,
        pool_size=8,
        n_gold=2,
        baseline=metrics(reciprocal_baseline),
        rerank=metrics(reciprocal_rerank),
    )


# ---------------------------------------------------------------------------
# Case loading / pool construction
# ---------------------------------------------------------------------------


async def test_load_cases_covers_en_de_fr_with_language_dimension() -> None:
    cases = load_cases()
    languages = {case.language for case in cases}
    names = {case.name for case in cases}
    assert languages == {"en", "de", "fr"}
    assert {"tone-soften", "voice-character"} <= names  # from the ADR-032 dataset
    assert {"tone-soften-de", "voice-character-de", "tone-soften-fr"} <= names


def test_case_blocks_labels_gold_by_position_and_skips_empty() -> None:
    case = next(case for case in load_cases() if case.name == "tone-soften")
    blocks = case_blocks(case)
    assert [block.position for block in blocks] == ["before", "after"]
    assert all(block.is_gold for block in blocks)


def test_build_pool_gold_first_distractors_only_from_other_cases() -> None:
    cases = load_cases()
    case = cases[0]
    pool = build_pool(case, cases, seed=90, n_distractors=6)
    assert len(pool) == 8  # 2 gold + 6 distractors
    gold, distractors = pool[:2], pool[2:]
    assert all(block.is_gold for block in gold)
    assert all(not block.is_gold for block in distractors)
    assert all(block.origin_case != case.name for block in distractors)
    assert {block.block_id for block in gold} == {f"{case.name}:before", f"{case.name}:after"}


def test_build_pool_same_seed_is_deterministic() -> None:
    cases = load_cases()
    first = build_pool(cases[0], cases, seed=90, n_distractors=6)
    second = build_pool(cases[0], cases, seed=90, n_distractors=6)
    assert [block.block_id for block in first] == [block.block_id for block in second]


# ---------------------------------------------------------------------------
# Scoring arms
# ---------------------------------------------------------------------------


def test_lexical_surrogate_identical_text_is_one_disjoint_is_zero() -> None:
    assert lexical_surrogate("the council room", "The council room!") == 1.0
    assert lexical_surrogate("council", "pferd") == 0.0


def test_seeded_scores_deterministic_bounded_and_seed_sensitive() -> None:
    first = seeded_scores("query", ["a", "b"], seed=90)
    second = seeded_scores("query", ["a", "b"], seed=90)
    other_seed = seeded_scores("query", ["a", "b"], seed=91)
    assert first == second
    assert all(0.0 <= score <= 1.0 for score in first)
    assert first != other_seed


async def test_rerank_arm_dry_run_reorders_by_seeded_scores() -> None:
    candidates = [
        _candidate("b block", 0.5),
        _candidate("a block", 0.9),
        _candidate("c block", 0.1),
    ]
    order = await rerank_arm("query", candidates, reranker=None, seed=90)
    scores = seeded_scores("query", [candidate.text for candidate in candidates], seed=90)
    scored = sorted(zip(scores, candidates, strict=True), key=lambda pair: pair[0], reverse=True)
    assert [candidate.source_id for candidate in order] == [
        candidate.source_id for _, candidate in scored
    ]


async def test_try_real_reranker_without_extra_degrades_with_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import evals.rerank_pilot as pilot

    monkeypatch.setattr(pilot, "is_rerank_available", lambda: False)
    reranker, reason = await try_real_reranker("lightonai/LateOn")
    assert reranker is None
    assert "sentence-transformers" in reason  # RULE-11: degradation carries its reason


# ---------------------------------------------------------------------------
# Metrics / summary
# ---------------------------------------------------------------------------


def test_order_metrics_best_gold_rank_and_recall() -> None:
    gold_a, gold_b, noise = _candidate("a", 1.0), _candidate("b", 1.0), _candidate("n", 1.0)
    order = [noise, gold_a, noise, gold_b]
    metrics = OrderMetrics.of(order, {gold_a.source_id, gold_b.source_id})
    assert metrics.gold_ranks == (2, 4)
    assert metrics.best_gold_rank == 2
    assert metrics.reciprocal_rank == 0.5
    assert metrics.recall_at_3 == 1.0  # best gold within top RECALL_K


def test_order_metrics_without_gold_is_zero() -> None:
    metrics = OrderMetrics.of([], set())
    assert metrics.best_gold_rank == 0
    assert metrics.reciprocal_rank == 0.0
    assert metrics.recall_at_3 == 0.0
    assert metrics.gold_ranks == ()


def test_classify_verdict_thresholds() -> None:
    assert classify_verdict(0.06) == "helps"
    assert classify_verdict(-0.06) == "hurts"
    assert classify_verdict(0.02) == "neutral"


def test_summarize_aggregates_mrr_and_verdict() -> None:
    summary = summarize([_case_result(1.0, 0.5), _case_result(0.5, 1.0)], with_verdict=True)
    assert summary.n_cases == 2
    assert summary.mrr_baseline == pytest.approx(0.75)
    assert summary.mrr_rerank == pytest.approx(0.75)
    assert summary.mrr_delta == pytest.approx(0.0)
    assert summary.verdict == "neutral"


def test_summarize_per_language_row_has_no_verdict() -> None:
    summary = summarize([_case_result(1.0, 1.0, language="de")], with_verdict=False)
    assert summary.verdict is None
    assert summary.n_cases == 1


# ---------------------------------------------------------------------------
# Dry-run end-to-end smoke (no checkpoint, no network)
# ---------------------------------------------------------------------------


async def test_run_pilot_dry_run_writes_marked_report(tmp_path: Path) -> None:
    output = tmp_path / "rerank_pilot.json"
    report = await run_pilot(output=output, dry_run=True)

    assert report.mode == "dry-run"
    assert report.rerank_model.startswith("fake:")
    assert {result.language for result in report.cases} == {"en", "de", "fr"}

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["mode"] == "dry-run"
    assert "Dormant wiring" in payload["wiring_status"]
    assert "textless_merge_v1" in payload["methodology"]
    assert payload["summary"]["verdict"] in {"helps", "hurts", "neutral"}
    assert len(payload["cases"]) == 6
    assert not output.with_name(output.name + ".tmp").exists()  # atomic replace cleaned up


def test_to_candidate_stable_ids() -> None:
    block = Block(
        block_id="case:before", text="t", is_gold=True, origin_case="case", position="before"
    )
    first = to_candidate(block, 0.5)
    second = to_candidate(block, 0.5)
    assert first.source_id == second.source_id
    assert first.source_type == "case:before"
    assert first.base_score == 0.5
